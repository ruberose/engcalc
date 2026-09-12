"""
찾기 기능 검증 — 메인 캔버스(canvas/document_scene.py의 find_blocks(),
ui/find_dialog.py)와 도움말 창(ui/help_dialog.py) 양쪽 모두.

사용자 요청: "찾기 기능 만들자. 메인 화면에서도 작동하지만, 도움말에서도
작동해야돼"
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication, QTabWidget

from app.main_window import MainWindow
from blocks.image_block import ImageBlock
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene
from ui.find_dialog import FindDialog
from ui.help_dialog import HelpDialog

_app = QApplication.instance() or QApplication([])


# --- DocumentScene.find_blocks() ---


def test_find_blocks_matches_math_block_input_text():
    """수식 블록은 입력 원문(계산 결과가 아니라)을 기준으로 찾아야 한다."""
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    block.set_input_text("F_y = 300")
    scene.addItem(block)

    assert scene.find_blocks("F_y") == [block]
    assert scene.find_blocks("300") == [block]


def test_find_blocks_matches_text_block_content():
    """텍스트 블록은 본문 내용으로 찾아야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(0, 0))
    block.set_text("강재 항복강도")
    scene.addItem(block)

    assert scene.find_blocks("항복강도") == [block]


def test_find_blocks_matches_image_caption():
    """이미지 블록은 캡션으로 찾아야 한다."""
    scene = DocumentScene()
    block = ImageBlock(position=(0, 0), caption="단면도")
    scene.addItem(block)

    assert scene.find_blocks("단면") == [block]


def test_find_blocks_is_case_insensitive():
    """대소문자를 구분하지 않아야 한다."""
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    block.set_input_text("Sigma_allow = 24")
    scene.addItem(block)

    assert scene.find_blocks("sigma") == [block]
    assert scene.find_blocks("SIGMA") == [block]


def test_find_blocks_empty_query_returns_empty_list():
    """빈 검색어는 아무것도 찾지 않아야 한다(전체 블록 나열 방지)."""
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    scene.addItem(block)

    assert scene.find_blocks("") == []
    assert scene.find_blocks("   ") == []


def test_find_blocks_orders_top_to_bottom():
    """여러 개 찾으면 화면 위→아래(같은 높이면 왼→오른) 순서로 정렬되어야 한다."""
    scene = DocumentScene()
    bottom = MathBlock(position=(0, 200))
    bottom.set_input_text("target = 1")
    top = MathBlock(position=(0, 0))
    top.set_input_text("target = 2")
    scene.addItem(bottom)
    scene.addItem(top)

    assert scene.find_blocks("target") == [top, bottom]


def test_find_blocks_no_match_returns_empty_list():
    """검색어와 일치하는 블록이 없으면 빈 리스트를 돌려줘야 한다."""
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    scene.addItem(block)

    assert scene.find_blocks("존재하지않는검색어") == []


# --- FindDialog (캔버스) ---


def test_find_dialog_selects_and_shows_match_count():
    """검색어를 입력하면 첫 번째 결과가 선택되고 "1 / n" 상태가 표시되어야 한다."""
    scene = DocumentScene()
    view = _make_view(scene)
    block = MathBlock(position=(0, 0))
    block.set_input_text("F_y = 300")
    scene.addItem(block)

    dialog = FindDialog(scene, view)
    dialog._input.setText("F_y")

    assert block.isSelected()
    assert dialog._status_label.text() == "1 / 1"
    dialog.close()


def test_find_dialog_next_wraps_around():
    """"다음"은 마지막 결과에서 다시 처음으로 돌아가야 한다(원형)."""
    scene = DocumentScene()
    view = _make_view(scene)
    first = MathBlock(position=(0, 0))
    first.set_input_text("target = 1")
    second = MathBlock(position=(0, 100))
    second.set_input_text("target = 2")
    scene.addItem(first)
    scene.addItem(second)

    dialog = FindDialog(scene, view)
    dialog._input.setText("target")
    assert first.isSelected()

    dialog.find_next()
    assert second.isSelected()
    assert not first.isSelected()

    dialog.find_next()  # 마지막에서 다시 처음으로
    assert first.isSelected()
    dialog.close()


def test_find_dialog_no_match_shows_message_and_clears_selection():
    """검색 결과가 없으면 안내 문구가 뜨고 선택이 해제되어야 한다."""
    scene = DocumentScene()
    view = _make_view(scene)
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    scene.addItem(block)
    block.setSelected(True)

    dialog = FindDialog(scene, view)
    dialog._input.setText("존재하지않음")

    assert not block.isSelected()
    assert dialog._status_label.text() == "검색 결과 없음"
    dialog.close()


def _make_view(scene: DocumentScene):
    from canvas.document_view import DocumentView

    return DocumentView(scene)


# --- MainWindow 배선 ---


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
    win._autosave_timer.stop()
    win._is_modified = False
    win.close()
    _app.processEvents()
    del win
    gc.collect()
    _app.processEvents()


def test_find_menu_action_uses_standard_shortcut(window):
    """찾기 메뉴 항목은 플랫폼 표준 단축키(Ctrl+F)를 써야 한다."""
    from PySide6.QtGui import QKeySequence

    edit_menu = window.menuBar().actions()[1].menu()  # 파일/편집/보기/도움말 순서
    find_actions = [a for a in edit_menu.actions() if "찾기" in a.text()]
    assert len(find_actions) == 1
    assert find_actions[0].shortcut() == QKeySequence.StandardKey.Find


def test_show_find_creates_and_reuses_same_dialog(window):
    """찾기를 여러 번 열어도 같은 창을 재사용해야 한다."""
    assert window._find_dialog is None
    window._on_show_find()
    _app.processEvents()
    first = window._find_dialog
    assert first.isVisible()

    window._on_show_find()
    _app.processEvents()
    assert window._find_dialog is first
    window._find_dialog.close()


def test_show_find_locates_block_in_real_canvas(window):
    """실제 MainWindow의 캔버스에 있는 블록을 찾기 창으로 찾을 수 있어야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("F_y = 300")
    window._scene.addItem(block)

    window._on_show_find()
    _app.processEvents()
    window._find_dialog._input.setText("F_y")

    assert block.isSelected()
    window._find_dialog.close()


# --- HelpDialog 안의 찾기 ---


def test_help_dialog_has_search_bar():
    """도움말 창에도 검색창이 있어야 한다(메인 창과는 별개의 최상위 창이므로)."""
    dialog = HelpDialog()
    assert dialog._search_input is not None
    dialog.close()


def test_help_dialog_find_next_highlights_text_in_active_tab():
    """도움말 검색은 지금 보이는 탭의 텍스트를 찾아 커서로 선택(하이라이트)해야 한다."""
    dialog = HelpDialog()
    tabs = dialog.findChild(QTabWidget)
    tabs.setCurrentIndex(1)  # "수식 작성법" 탭 — "LaTeX"가 있는 곳

    dialog._search_input.setText("LaTeX")

    browser = tabs.currentWidget()
    assert browser.textCursor().hasSelection()
    assert browser.textCursor().selectedText().lower() == "latex"
    dialog.close()


def test_help_dialog_search_with_no_match_shows_message():
    """도움말 창에서 없는 단어를 검색하면 "검색 결과 없음"이 떠야 한다."""
    dialog = HelpDialog()
    dialog._search_input.setText("존재하지않는단어xyz123")
    assert dialog._search_status.text() == "검색 결과 없음"
    dialog.close()


def test_help_dialog_ctrl_f_shortcut_focuses_search_input():
    """Ctrl+F는 검색창에 포커스를 줘야 한다."""
    dialog = HelpDialog()
    dialog.show()
    _app.processEvents()

    dialog._focus_search()
    assert dialog._search_input.hasFocus()
    dialog.close()
