"""
블록 간격 균등 배치(메뉴 > 편집 > 정렬 > 가로/세로 간격 균등) 기능 검증.

사용자 요청: "여러 블록 간격을 똑같이 맞추고 싶다" — 정렬(왼쪽/오른쪽 맞춤 등)은
이미 있지만, 여러 블록을 일정한 간격으로 쫙 펼치는 기능은 없었다. 정렬과 같은
패턴(양 끝은 고정, 사이 블록만 재배치, 실행취소 가능, 재계산 트리거)을 따른다.
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene

_app = QApplication.instance() or QApplication([])


def _make_scene_with_three_blocks():
    scene = DocumentScene()
    a = TextBlock(position=(0, 0))
    a.set_text("A")
    b = TextBlock(position=(50, 0))
    b.set_text("B")
    c = TextBlock(position=(400, 0))
    c.set_text("C")
    for block in (a, b, c):
        scene.addItem(block)
    return scene, a, b, c


def _select(*blocks):
    for block in blocks:
        block.setSelected(True)


def test_distribute_horizontal_keeps_endpoints_fixed():
    scene, a, b, c = _make_scene_with_three_blocks()
    original_a_x, original_c_x = a.pos().x(), c.pos().x()

    _select(a, b, c)
    scene.distribute_selected_blocks("horizontal")

    assert a.pos().x() == original_a_x
    assert c.pos().x() == original_c_x


def test_distribute_horizontal_produces_equal_gaps():
    scene, a, b, c = _make_scene_with_three_blocks()

    _select(a, b, c)
    scene.distribute_selected_blocks("horizontal")

    ordered = sorted((a, b, c), key=lambda blk: blk.pos().x())
    gap1 = ordered[1].pos().x() - (ordered[0].pos().x() + ordered[0].boundingRect().width())
    gap2 = ordered[2].pos().x() - (ordered[1].pos().x() + ordered[1].boundingRect().width())
    assert abs(gap1 - gap2) < 1e-6


def test_distribute_horizontal_does_not_change_y():
    scene, a, b, c = _make_scene_with_three_blocks()
    original_ys = [block.pos().y() for block in (a, b, c)]

    _select(a, b, c)
    scene.distribute_selected_blocks("horizontal")

    assert [block.pos().y() for block in (a, b, c)] == original_ys


def test_distribute_vertical_produces_equal_gaps():
    scene = DocumentScene()
    a = TextBlock(position=(0, 0))
    a.set_text("A")
    b = TextBlock(position=(0, 40))
    b.set_text("B")
    c = TextBlock(position=(0, 300))
    c.set_text("C")
    for block in (a, b, c):
        scene.addItem(block)

    _select(a, b, c)
    scene.distribute_selected_blocks("vertical")

    ordered = sorted((a, b, c), key=lambda blk: blk.pos().y())
    gap1 = ordered[1].pos().y() - (ordered[0].pos().y() + ordered[0].boundingRect().height())
    gap2 = ordered[2].pos().y() - (ordered[1].pos().y() + ordered[1].boundingRect().height())
    assert abs(gap1 - gap2) < 1e-6


def test_distribute_with_fewer_than_three_selected_does_nothing():
    scene, a, b, c = _make_scene_with_three_blocks()
    original = (b.pos().x(), b.pos().y())

    _select(a, b)  # 2개뿐
    scene.distribute_selected_blocks("horizontal")

    assert (b.pos().x(), b.pos().y()) == original


def test_distribute_with_unknown_mode_does_nothing():
    scene, a, b, c = _make_scene_with_three_blocks()
    original_positions = [(block.pos().x(), block.pos().y()) for block in (a, b, c)]

    _select(a, b, c)
    scene.distribute_selected_blocks("diagonal")

    assert [(block.pos().x(), block.pos().y()) for block in (a, b, c)] == original_positions


def test_distribute_ignores_locked_blocks():
    scene, a, b, c = _make_scene_with_three_blocks()
    b.set_locked(True)
    original_b_pos = (b.pos().x(), b.pos().y())

    _select(a, b, c)
    scene.distribute_selected_blocks("horizontal")

    assert (b.pos().x(), b.pos().y()) == original_b_pos


def test_distribute_is_undoable():
    scene, a, b, c = _make_scene_with_three_blocks()
    original_b_x = b.pos().x()
    b_id = b.block_id

    _select(a, b, c)
    scene.distribute_selected_blocks("horizontal")
    assert b.pos().x() != original_b_x

    assert scene.can_undo()
    scene.undo()

    restored_b = next(item for item in scene.items() if getattr(item, "block_id", None) == b_id)
    assert restored_b.pos().x() == original_b_x


# --- 메뉴 > 편집 > 정렬 > 간격 균등 연동 ---


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


def test_distribute_menu_has_two_actions(window):
    assert len(window._distribute_actions) == 2
    labels = {a.text() for a in window._distribute_actions}
    assert labels == {"가로 간격 균등", "세로 간격 균등"}


def test_distribute_actions_disabled_with_fewer_than_three_selected(window):
    first = MathBlock(position=(0, 0))
    second = MathBlock(position=(100, 100))
    window._scene.addItem(first)
    window._scene.addItem(second)
    first.setSelected(True)
    second.setSelected(True)
    window._update_edit_menu_state()

    assert all(not a.isEnabled() for a in window._distribute_actions)


def test_distribute_actions_enabled_with_three_or_more_selected(window):
    blocks = [MathBlock(position=(i * 100, 0)) for i in range(3)]
    for block in blocks:
        window._scene.addItem(block)
        block.setSelected(True)
    window._update_edit_menu_state()

    assert all(a.isEnabled() for a in window._distribute_actions)


def test_on_distribute_calls_scene_with_correct_mode(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window._scene, "distribute_selected_blocks", lambda mode: calls.append(mode))

    window._on_distribute("vertical")

    assert calls == ["vertical"]


def test_on_distribute_ignored_while_editing_text(window, monkeypatch):
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    calls = []
    monkeypatch.setattr(window._scene, "distribute_selected_blocks", lambda mode: calls.append(mode))

    window._on_distribute("horizontal")

    assert calls == []

    block.finish_editing()
