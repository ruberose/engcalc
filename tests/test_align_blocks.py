"""
블록 정렬(메뉴 > 편집 > 정렬) 기능 검증.

사용자 요청: "블록 정렬/맞추기 (여러 개 선택해서 좌측 정렬 등)"

설계: 기준은 항상 "선택된 블록들 전체를 감싸는 사각형"이다 — 어느 한
블록을 "기준"으로 따로 고르지 않는다(canvas/document_scene.py의
align_selected_blocks() 참고).
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene

_app = QApplication.instance() or QApplication([])


# --- DocumentScene.align_selected_blocks() ---


def _make_scene_with_three_blocks():
    scene = DocumentScene()
    a = TextBlock(position=(10, 10))
    a.set_text("A")
    b = TextBlock(position=(120, 80))
    b.set_text("긴 텍스트 블록 B")
    c = TextBlock(position=(300, 5))
    c.set_text("C 블록")
    for block in (a, b, c):
        scene.addItem(block)
    return scene, a, b, c


def _select(*blocks):
    for block in blocks:
        block.setSelected(True)


def test_align_left_matches_leftmost_original_edge():
    scene, a, b, c = _make_scene_with_three_blocks()
    expected = min(block.pos().x() for block in (a, b, c))

    _select(a, b, c)
    scene.align_selected_blocks("left")

    for block in (a, b, c):
        assert block.pos().x() == expected
    assert a.pos().y() == 10  # y좌표는 안 바뀌어야 한다
    assert c.pos().y() == 5


def test_align_right_matches_rightmost_original_edge():
    scene, a, b, c = _make_scene_with_three_blocks()
    expected = max(block.pos().x() + block.boundingRect().width() for block in (a, b, c))

    _select(a, b, c)
    scene.align_selected_blocks("right")

    for block in (a, b, c):
        assert abs(block.pos().x() + block.boundingRect().width() - expected) < 1e-6


def test_align_top_matches_topmost_original_edge():
    scene, a, b, c = _make_scene_with_three_blocks()
    expected = min(block.pos().y() for block in (a, b, c))

    _select(a, b, c)
    scene.align_selected_blocks("top")

    for block in (a, b, c):
        assert block.pos().y() == expected


def test_align_bottom_matches_bottommost_original_edge():
    scene, a, b, c = _make_scene_with_three_blocks()
    expected = max(block.pos().y() + block.boundingRect().height() for block in (a, b, c))

    _select(a, b, c)
    scene.align_selected_blocks("bottom")

    for block in (a, b, c):
        assert abs(block.pos().y() + block.boundingRect().height() - expected) < 1e-6


def test_align_center_h_centers_on_selection_bounding_box():
    scene, a, b, c = _make_scene_with_three_blocks()
    lefts = [block.pos().x() for block in (a, b, c)]
    rights = [block.pos().x() + block.boundingRect().width() for block in (a, b, c)]
    expected_center = (min(lefts) + max(rights)) / 2

    _select(a, b, c)
    scene.align_selected_blocks("center_h")

    for block in (a, b, c):
        center = block.pos().x() + block.boundingRect().width() / 2
        assert abs(center - expected_center) < 1e-6


def test_align_center_v_centers_on_selection_bounding_box():
    scene, a, b, c = _make_scene_with_three_blocks()
    tops = [block.pos().y() for block in (a, b, c)]
    bottoms = [block.pos().y() + block.boundingRect().height() for block in (a, b, c)]
    expected_center = (min(tops) + max(bottoms)) / 2

    _select(a, b, c)
    scene.align_selected_blocks("center_v")

    for block in (a, b, c):
        center = block.pos().y() + block.boundingRect().height() / 2
        assert abs(center - expected_center) < 1e-6


def test_align_with_fewer_than_two_selected_does_nothing():
    scene, a, b, c = _make_scene_with_three_blocks()
    original = (a.pos().x(), a.pos().y())

    a.setSelected(True)  # 딱 하나만 선택
    scene.align_selected_blocks("left")

    assert (a.pos().x(), a.pos().y()) == original


def test_align_with_unknown_mode_does_nothing():
    scene, a, b, c = _make_scene_with_three_blocks()
    original_positions = [(block.pos().x(), block.pos().y()) for block in (a, b, c)]

    _select(a, b, c)
    scene.align_selected_blocks("diagonal")  # 존재하지 않는 모드

    assert [(block.pos().x(), block.pos().y()) for block in (a, b, c)] == original_positions


def test_align_is_undoable():
    scene, a, b, c = _make_scene_with_three_blocks()
    original_b_x = b.pos().x()
    b_id = b.block_id

    _select(a, b, c)
    scene.align_selected_blocks("left")
    assert b.pos().x() != original_b_x

    assert scene.can_undo()
    scene.undo()

    # undo()는 씬을 통째로 지우고 스냅샷에서 새 블록 객체로 복원하므로(문서 전체
    # 스냅샷 방식 — canvas/document_scene.py의 undo() 참고), 정렬 전의 b는 더 이상
    # 유효한 객체가 아니다. id로 복원된 블록을 다시 찾아서 확인해야 한다.
    restored_b = next(item for item in scene.items() if getattr(item, "block_id", None) == b_id)
    assert restored_b.pos().x() == original_b_x


def test_align_triggers_recalculation():
    """정렬로 화면상 위→아래 순서가 바뀔 수 있으므로, 정렬 뒤엔 항상 다시 계산해야 한다."""
    scene, a, b, c = _make_scene_with_three_blocks()
    calls: list[int] = []
    original_recalculate = scene.recalculate_all
    scene.recalculate_all = lambda: (calls.append(1), original_recalculate())[-1]

    _select(a, b, c)
    scene.align_selected_blocks("left")

    assert calls == [1]


# --- 메뉴 > 편집 > 정렬 연동 ---


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


def test_align_menu_has_six_actions(window):
    assert len(window._align_actions) == 6
    labels = {a.text() for a in window._align_actions}
    assert labels == {"왼쪽 맞춤", "가운데 맞춤", "오른쪽 맞춤", "위쪽 맞춤", "중간 맞춤", "아래쪽 맞춤"}


def test_align_actions_disabled_with_fewer_than_two_selected(window):
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    block.setSelected(True)
    window._update_edit_menu_state()

    assert all(not a.isEnabled() for a in window._align_actions)


def test_align_actions_enabled_with_two_or_more_selected(window):
    first = MathBlock(position=(0, 0))
    first.set_input_text("a = 1")
    second = MathBlock(position=(100, 100))
    second.set_input_text("b = 2")
    window._scene.addItem(first)
    window._scene.addItem(second)
    first.setSelected(True)
    second.setSelected(True)
    window._update_edit_menu_state()

    assert all(a.isEnabled() for a in window._align_actions)


def test_on_align_calls_scene_with_correct_mode(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window._scene, "align_selected_blocks", lambda mode: calls.append(mode))

    window._on_align("center_h")

    assert calls == ["center_h"]


def test_on_align_ignored_while_editing_text(window, monkeypatch):
    """편집 중(텍스트 커서가 활성)일 때는 정렬 단축키/메뉴가 편집기 동작을 방해하면 안 된다."""
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    calls = []
    monkeypatch.setattr(window._scene, "align_selected_blocks", lambda mode: calls.append(mode))

    window._on_align("left")

    assert calls == []
