"""
여러 블록 글자 크기 한 번에 조절(메뉴 > 편집 > 글자 크게/작게, Ctrl+]/Ctrl+[) 검증.

사용자 요청: 블록마다 글자 크기를 따로 조절하는 기능은 있었지만(property_panel),
여러 개를 선택했을 때 한 번에 키우고 줄이는 건 안 됐다. document_scene.py의
adjust_font_size_for_selected()가 새로 담당한다.
"""

import gc

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene, _MAX_FONT_SIZE, _MIN_FONT_SIZE

_app = QApplication.instance() or QApplication([])


def test_adjust_font_size_increases_all_selected():
    scene = DocumentScene()
    a = TextBlock(position=(0, 0))
    b = MathBlock(position=(0, 50))
    scene.addItem(a)
    scene.addItem(b)
    a.setSelected(True)
    b.setSelected(True)
    original_a, original_b = a.font_size(), b.font_size()

    changed = scene.adjust_font_size_for_selected(4)

    assert changed == 2
    assert a.font_size() == original_a + 4
    assert b.font_size() == original_b + 4


def test_adjust_font_size_decreases_all_selected():
    scene = DocumentScene()
    a = TextBlock(position=(0, 0))
    scene.addItem(a)
    a.setSelected(True)
    original = a.font_size()

    scene.adjust_font_size_for_selected(-4)

    assert a.font_size() == original - 4


def test_adjust_font_size_clamps_to_max():
    scene = DocumentScene()
    a = TextBlock(position=(0, 0))
    a.set_font_size(_MAX_FONT_SIZE - 1)
    scene.addItem(a)
    a.setSelected(True)

    scene.adjust_font_size_for_selected(10)

    assert a.font_size() == _MAX_FONT_SIZE


def test_adjust_font_size_clamps_to_min():
    scene = DocumentScene()
    a = TextBlock(position=(0, 0))
    a.set_font_size(_MIN_FONT_SIZE + 1)
    scene.addItem(a)
    a.setSelected(True)

    scene.adjust_font_size_for_selected(-10)

    assert a.font_size() == _MIN_FONT_SIZE


def test_adjust_font_size_ignores_locked_blocks():
    scene = DocumentScene()
    a = TextBlock(position=(0, 0))
    a.set_locked(True)
    scene.addItem(a)
    a.setSelected(True)
    original = a.font_size()

    changed = scene.adjust_font_size_for_selected(4)

    assert changed == 0
    assert a.font_size() == original


def test_adjust_font_size_ignores_non_text_math_blocks():
    scene = DocumentScene()
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    image.fill(QColor(0, 0, 0))
    block = scene.create_image_block_from_pixmap(QPointF(0, 0), QPixmap.fromImage(image))
    block.setSelected(True)

    changed = scene.adjust_font_size_for_selected(4)

    assert changed == 0


def test_adjust_font_size_with_nothing_selected_returns_zero():
    scene = DocumentScene()
    assert scene.adjust_font_size_for_selected(4) == 0


def test_adjust_font_size_is_undoable():
    scene = DocumentScene()
    a = TextBlock(position=(0, 0))
    scene.addItem(a)
    a.setSelected(True)
    original = a.font_size()
    a_id = a.block_id

    scene.adjust_font_size_for_selected(4)
    assert scene.can_undo()
    scene.undo()

    restored = next(item for item in scene.items() if getattr(item, "block_id", None) == a_id)
    assert restored.font_size() == original


# --- 메뉴 > 편집 > 글자 크게/작게 연동 ---


@pytest.fixture
def window():
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


def test_font_size_actions_disabled_with_nothing_selected(window):
    window._update_edit_menu_state()
    assert not window._increase_font_action.isEnabled()
    assert not window._decrease_font_action.isEnabled()


def test_font_size_actions_enabled_with_text_block_selected(window):
    block = TextBlock(position=(0, 0))
    window._scene.addItem(block)
    block.setSelected(True)
    window._update_edit_menu_state()

    assert window._increase_font_action.isEnabled()
    assert window._decrease_font_action.isEnabled()


def test_on_adjust_font_size_calls_scene(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window._scene, "adjust_font_size_for_selected", lambda delta: calls.append(delta) or 1)

    window._on_adjust_font_size(2)

    assert calls == [2]


def test_on_adjust_font_size_ignored_while_editing_text(window, monkeypatch):
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    calls = []
    monkeypatch.setattr(window._scene, "adjust_font_size_for_selected", lambda delta: calls.append(delta) or 1)

    window._on_adjust_font_size(2)

    assert calls == []

    block.finish_editing()
