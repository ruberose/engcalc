"""
블록 잠금 기능 검증 (메뉴 > 편집 > 블록 잠그기/블록 잠금 해제).

사용자 요청: "블록 잠금" — 완성된 계산 블록을 실수로 드래그/수정/삭제하지
못하게 보호한다. 이동(ItemIsMovable)은 Qt가 알아서 막아주고, 편집 진입/
크기조절/삭제는 각 블록·뷰가 is_locked()를 직접 확인해서 막는다.
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication, QGraphicsItem

from app.main_window import MainWindow
from blocks.image_block import ImageBlock
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene

_app = QApplication.instance() or QApplication([])


# --- BaseBlock.set_locked()/is_locked() 공통 동작 ---


def test_block_starts_unlocked():
    block = MathBlock(position=(0, 0))
    assert not block.is_locked()


def test_set_locked_true_disables_movable_flag():
    block = MathBlock(position=(0, 0))
    block.set_locked(True)
    assert block.is_locked()
    assert not (block.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable)


def test_set_locked_false_restores_movable_flag():
    block = MathBlock(position=(0, 0))
    block.set_locked(True)
    block.set_locked(False)
    assert not block.is_locked()
    assert bool(block.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable)


def test_locked_block_remains_selectable():
    """잠긴 블록도 선택은 계속 가능해야 한다(잠금 해제하려면 선택할 수 있어야 함)."""
    block = MathBlock(position=(0, 0))
    block.set_locked(True)
    assert bool(block.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)


def test_locked_state_round_trips_through_serialize():
    block = MathBlock(position=(0, 0))
    block.set_locked(True)
    data = block.serialize()
    assert data["locked"] is True

    restored = MathBlock(position=(0, 0))
    restored.deserialize(data)
    assert restored.is_locked()


def test_unlocked_state_round_trips_through_serialize():
    block = MathBlock(position=(0, 0))
    data = block.serialize()
    assert data["locked"] is False


def test_loading_old_block_data_without_locked_field_defaults_to_unlocked():
    """잠금 필드가 없는 옛 파일(하위 호환)은 잠금 해제 상태로 열려야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    data = block.serialize()
    del data["locked"]

    restored = MathBlock(position=(0, 0))
    restored.deserialize(data)
    assert not restored.is_locked()


# --- 편집 진입 차단 ---


def test_locked_math_block_ignores_start_editing():
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    block.set_locked(True)

    block.start_editing()

    assert block._editor is None


def test_locked_text_block_ignores_start_editing():
    block = TextBlock(position=(0, 0))
    block.set_locked(True)

    block.start_editing()

    assert block._editor is None


def test_unlocked_math_block_can_still_start_editing():
    block = MathBlock(position=(0, 0))
    block.start_editing()
    assert block._editor is not None
    block.finish_editing()


# --- DocumentScene: 선택 잠그기/잠금 해제 ---


def test_set_locked_for_selected_locks_only_selected_blocks():
    scene = DocumentScene()
    a = MathBlock(position=(0, 0))
    b = MathBlock(position=(0, 60))
    scene.addItem(a)
    scene.addItem(b)
    a.setSelected(True)

    scene.set_locked_for_selected(True)

    assert a.is_locked()
    assert not b.is_locked()


def test_set_locked_for_selected_with_nothing_selected_does_nothing():
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    scene.addItem(block)

    scene.set_locked_for_selected(True)

    assert not block.is_locked()


def test_lock_is_undoable():
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    scene.addItem(block)
    block.setSelected(True)

    scene.set_locked_for_selected(True)
    assert block.is_locked()
    assert scene.can_undo()

    scene.undo()
    restored = next(item for item in scene.items() if isinstance(item, MathBlock))
    assert not restored.is_locked()


def test_align_selected_blocks_skips_locked_blocks():
    """잠긴 블록은 정렬 대상/기준에서 빠진다."""
    scene = DocumentScene()
    locked = TextBlock(position=(500, 0))
    locked.set_locked(True)
    a = TextBlock(position=(10, 10))
    b = TextBlock(position=(100, 20))
    scene.addItem(locked)
    scene.addItem(a)
    scene.addItem(b)

    for block in (locked, a, b):
        block.setSelected(True)

    scene.align_selected_blocks("left")

    assert locked.pos().x() == 500  # 잠긴 블록은 그대로
    assert a.pos().x() == b.pos().x()  # 나머지 둘만 정렬됨


# --- DocumentView: 삭제 차단 ---


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


def test_delete_key_does_not_remove_locked_block(window):
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    block.set_locked(True)
    block.setSelected(True)

    window._view._delete_selected_blocks()

    assert block in window._scene.items()


def test_delete_key_removes_unlocked_block_alongside_locked_one(window):
    """잠긴 블록과 안 잠긴 블록을 같이 선택해서 지우면, 안 잠긴 것만 지워져야 한다."""
    locked = MathBlock(position=(0, 0))
    locked.set_input_text("a = 1")
    window._scene.addItem(locked)
    locked.set_locked(True)

    unlocked = MathBlock(position=(0, 60))
    unlocked.set_input_text("b = 2")
    window._scene.addItem(unlocked)

    locked.setSelected(True)
    unlocked.setSelected(True)

    window._view._delete_selected_blocks()

    assert locked in window._scene.items()
    assert unlocked not in window._scene.items()


# --- 메뉴 연동 ---


def test_lock_menu_actions_enabled_based_on_selection_lock_state(window):
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.setSelected(True)
    window._update_edit_menu_state()

    assert window._lock_action.isEnabled()
    assert not window._unlock_action.isEnabled()

    window._on_set_locked(True)

    assert block.is_locked()
    assert not window._lock_action.isEnabled()
    assert window._unlock_action.isEnabled()


def test_lock_menu_actions_disabled_with_nothing_selected(window):
    assert not window._lock_action.isEnabled()
    assert not window._unlock_action.isEnabled()


def test_on_set_locked_ignored_while_editing_text(window):
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.setSelected(True)
    block.start_editing()
    _app.processEvents()

    window._on_set_locked(True)  # 편집 중이므로 무시되어야 함

    assert not block.is_locked()

    block.finish_editing()


# --- 그리기(paint) 예외 없이 동작하는지 스모크 테스트 ---


def test_locked_blocks_paint_without_crashing():
    """세 가지 블록 타입 모두 잠긴 상태로 예외 없이 그려져야 한다(자물쇠 배지 + 회색 테두리)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    scene = DocumentScene()
    math_block = MathBlock(position=(0, 0))
    math_block.set_input_text("a = 1")
    text_block = TextBlock(position=(0, 100))
    text_block.set_text("설명")
    image_block = ImageBlock(position=(0, 200))
    for block in (math_block, text_block, image_block):
        scene.addItem(block)
        block.set_locked(True)
        block.setSelected(True)
    scene.recalculate_all()

    image = QImage(400, 400, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    scene.render(painter, QRectF(0, 0, 400, 400), QRectF(0, 0, 400, 400))
    painter.end()
