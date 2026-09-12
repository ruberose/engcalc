"""
클립보드 이미지 붙여넣기(Ctrl+V) 기능 검증.

사용자 요청: "OS 클립보드 이미지 붙여넣기 (Ctrl+V로 스크린샷 바로 붙여넣기)"
— 스크린샷을 찍고 바로 Ctrl+V 하면 화면 중앙에 이미지 블록으로 붙여넣긴다.
내부 블록 클립보드(Ctrl+C로 복사한 블록)보다 우선한다.

tests/conftest.py의 autouse fixture(isolated_clipboard)가 QApplication.clipboard()를
가짜로 돌려두므로, 실제 OS 클립보드는 전혀 건드리지 않는다.
"""

import gc

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from blocks.image_block import ImageBlock
from blocks.math_block import MathBlock
from canvas.document_scene import DocumentScene

_app = QApplication.instance() or QApplication([])


def _sample_image(width: int = 40, height: int = 30) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(10, 20, 30))
    return image


# --- DocumentScene.create_image_block_from_pixmap() ---


def test_create_image_block_from_pixmap_adds_block():
    from PySide6.QtGui import QPixmap

    scene = DocumentScene()
    pixmap = QPixmap.fromImage(_sample_image())

    block = scene.create_image_block_from_pixmap(QPointF(10, 10), pixmap)

    assert block is not None
    assert block in scene.items()
    assert isinstance(block, ImageBlock)


def test_create_image_block_from_pixmap_with_null_pixmap_returns_none():
    from PySide6.QtGui import QPixmap

    scene = DocumentScene()
    block = scene.create_image_block_from_pixmap(QPointF(10, 10), QPixmap())
    assert block is None


def test_create_image_block_from_pixmap_is_undoable():
    from PySide6.QtGui import QPixmap

    scene = DocumentScene()
    pixmap = QPixmap.fromImage(_sample_image())
    scene.create_image_block_from_pixmap(QPointF(10, 10), pixmap)

    assert scene.can_undo()
    scene.undo()
    assert not any(isinstance(item, ImageBlock) for item in scene.items())


# --- MainWindow 연동 ---


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


def test_paste_with_clipboard_image_creates_image_block(window, isolated_clipboard):
    isolated_clipboard.set_image(_sample_image())

    window._on_paste()

    assert any(isinstance(item, ImageBlock) for item in window._scene.items())


def test_paste_with_no_clipboard_image_and_no_internal_clipboard_does_nothing(window):
    window._on_paste()
    assert not any(isinstance(item, ImageBlock) for item in window._scene.items())


def test_clipboard_image_takes_priority_over_internal_block_clipboard(window, isolated_clipboard):
    """복사해둔 블록이 있어도, 클립보드에 이미지가 있으면 이미지가 우선 붙여넣긴다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    block.setSelected(True)
    window._on_copy()
    assert window._scene.can_paste()

    isolated_clipboard.set_image(_sample_image())
    window._on_paste()

    math_blocks = [item for item in window._scene.items() if isinstance(item, MathBlock)]
    image_blocks = [item for item in window._scene.items() if isinstance(item, ImageBlock)]
    assert len(math_blocks) == 1  # 복제 안 됨
    assert len(image_blocks) == 1  # 대신 이미지가 붙여넣김


def test_falls_back_to_internal_clipboard_when_no_image(window):
    """클립보드에 이미지가 없으면 지금까지처럼 내부 블록 클립보드를 쓴다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    block.setSelected(True)
    window._on_copy()

    window._on_paste()

    assert len([item for item in window._scene.items() if isinstance(item, MathBlock)]) == 2


def test_pasted_image_is_placed_at_visible_center_and_selected(window, isolated_clipboard):
    isolated_clipboard.set_image(_sample_image())

    window._on_paste()

    image_block = next(item for item in window._scene.items() if isinstance(item, ImageBlock))
    assert image_block.isSelected()


def test_pasted_image_is_undoable(window, isolated_clipboard):
    isolated_clipboard.set_image(_sample_image())
    window._on_paste()
    assert any(isinstance(item, ImageBlock) for item in window._scene.items())

    window._scene.undo()

    assert not any(isinstance(item, ImageBlock) for item in window._scene.items())


def test_paste_action_enabled_when_clipboard_has_image(window, isolated_clipboard):
    window._update_edit_menu_state()
    assert not window._paste_action.isEnabled()

    isolated_clipboard.set_image(_sample_image())
    window._update_edit_menu_state()

    assert window._paste_action.isEnabled()


def test_paste_image_ignored_while_editing_text(window, isolated_clipboard):
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    isolated_clipboard.set_image(_sample_image())
    window._on_paste()  # 편집 중이므로 무시되어야 함

    assert not any(isinstance(item, ImageBlock) for item in window._scene.items())

    block.finish_editing()
