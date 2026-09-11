"""
편집 메뉴(실행취소/다시실행/복사/붙여넣기)의 MainWindow 수준 동작 검증.

canvas/document_scene.py의 실제 로직은 test_undo_redo_copy_paste.py가 다루므로,
여기서는 그 위에 얹힌 "메뉴/단축키" 배선이 실제로 잘 동작하는지에 집중한다.

버그체크 중 발견한 두 가지가 특히 중요해서 회귀 테스트로 남긴다:
1. QAction이 비활성(disabled) 상태면 단축키(Ctrl+Z 등)조차 동작하지 않는다.
   편집 메뉴를 한 번도 열지 않은 채 방금 만든 블록에 Ctrl+Z를 눌러도 실행취소가
   되어야 하므로, 활성 상태를 메뉴가 열릴 때(aboutToShow)뿐 아니라 실시간으로도
   맞춰줘야 한다.
2. MathBlock/TextBlock 자신도 ItemIsFocusable이라 "그냥 클릭"만 해도
   scene.focusItem()이 그 블록 자신이 될 수 있다. "편집 중"인지는 focusItem이
   실제 편집기(QGraphicsTextItem)인지로 구분해야 한다 — 안 그러면 블록을
   클릭하거나 드래그만 해도 Ctrl+Z/C/V가 먹통이 된다.
"""

import gc

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from blocks.math_block import MathBlock

_app = QApplication.instance() or QApplication([])


@pytest.fixture
def window():
    """테스트용 MainWindow 하나 (정리 방식은 test_recalculation_triggers.py의 동일 fixture 참고)."""
    win = MainWindow()
    win.show()
    for _ in range(3):
        _app.processEvents()
    yield win
    win._scene.selectionChanged.disconnect(win._on_selection_changed)
    win._scene.changed.disconnect(win._on_scene_changed)
    win._is_modified = False
    win.close()
    _app.processEvents()
    del win
    gc.collect()
    _app.processEvents()


def _add_math_block_via_ui(win: MainWindow, x: int, y: int, text: str) -> MathBlock:
    """실제 더블클릭 -> 입력 -> 편집 종료 흐름으로 수식 블록을 만든다."""
    view = win.centralWidget()
    scene = view.scene()
    before = {id(i) for i in scene.items() if isinstance(i, MathBlock)}
    QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos=QPoint(x, y))
    _app.processEvents()
    new_blocks = [i for i in scene.items() if isinstance(i, MathBlock) and id(i) not in before]
    assert len(new_blocks) == 1
    block = new_blocks[0]
    block._editor.setPlainText(text)
    block.finish_editing()
    _app.processEvents()
    return block


def _math_blocks(win: MainWindow) -> list[MathBlock]:
    return [i for i in win._scene.items() if isinstance(i, MathBlock)]


def test_shortcuts_use_platform_standard_keys(window):
    """단축키는 QKeySequence.StandardKey로 등록되어 있어야 한다(운영체제별 관례를 따름)."""
    assert window._undo_action.shortcut() == QKeySequence.StandardKey.Undo
    assert window._redo_action.shortcut() == QKeySequence.StandardKey.Redo
    assert window._copy_action.shortcut() == QKeySequence.StandardKey.Copy
    assert window._paste_action.shortcut() == QKeySequence.StandardKey.Paste


def test_undo_action_enabled_immediately_without_opening_menu(window):
    """
    메뉴를 한 번도 열지 않아도, 블록을 만들면 곧바로 실행취소 버튼이 활성화되어야 한다.

    (실행취소 메뉴를 aboutToShow에서만 갱신하던 버그: 방금 만든 블록에 Ctrl+Z를
    눌러도 액션이 비활성 상태로 굳어 있어 단축키 자체가 무시됐었다.)
    """
    assert not window._undo_action.isEnabled()
    _add_math_block_via_ui(window, 150, 100, "a = 1")
    assert window._undo_action.isEnabled()


def test_ctrl_z_keypress_undoes_block_creation_without_opening_menu(window):
    """편집 메뉴를 열지 않고 실제 Ctrl+Z 키 입력만으로 방금 만든 블록이 사라져야 한다."""
    _add_math_block_via_ui(window, 150, 100, "a = 1")
    assert len(_math_blocks(window)) == 1

    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    _app.processEvents()
    assert len(_math_blocks(window)) == 0


def test_ctrl_y_keypress_redoes_after_ctrl_z(window):
    """Ctrl+Z로 취소한 걸 Ctrl+Y로 다시 되돌릴 수 있어야 한다."""
    _add_math_block_via_ui(window, 150, 100, "a = 1")
    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    _app.processEvents()
    assert len(_math_blocks(window)) == 0

    QTest.keyClick(window, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    _app.processEvents()
    assert len(_math_blocks(window)) == 1


def test_clicking_block_does_not_block_undo_shortcut(window):
    """
    블록을 클릭(선택)만 해도 그 블록 자신이 scene.focusItem()이 될 수 있는데,
    그게 "편집 중"으로 오인되어 Ctrl+Z가 막히면 안 된다.
    """
    block = _add_math_block_via_ui(window, 150, 100, "a = 1")
    block.setSelected(True)
    _app.processEvents()

    assert not window._is_editing_text()

    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    _app.processEvents()
    assert len(_math_blocks(window)) == 0


def test_undo_ignored_while_actually_editing_text(window):
    """실제로 텍스트 편집 중일 때는 Ctrl+Z가 문서 실행취소로 넘어가면 안 된다."""
    block = _add_math_block_via_ui(window, 150, 100, "a = 1")
    block.start_editing()
    _app.processEvents()

    assert window._is_editing_text()

    window._on_undo()  # 편집 중이므로 무시되어야 함
    assert len(_math_blocks(window)) == 1  # 블록이 그대로 남아있어야 함

    block.finish_editing()


def test_copy_action_enables_paste_action_without_scene_change(window):
    """
    복사는 화면을 바꾸지 않아 scene.changed가 안 울리므로, 붙여넣기 활성화를
    복사 처리(_on_copy) 안에서 직접 갱신해줘야 한다.
    """
    block = _add_math_block_via_ui(window, 150, 100, "a = 1")
    block.setSelected(True)

    assert not window._paste_action.isEnabled()
    window._on_copy()
    assert window._paste_action.isEnabled()


def test_copy_paste_via_actions_duplicates_block(window):
    """복사 -> 붙여넣기 액션을 실제로 실행하면 블록이 하나 더 생겨야 한다."""
    block = _add_math_block_via_ui(window, 150, 100, "F = 200 kN")
    block.setSelected(True)

    window._on_copy()
    window._on_paste()
    _app.processEvents()

    assert len(_math_blocks(window)) == 2
