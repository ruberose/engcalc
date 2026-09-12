"""
결과값 복사(메뉴 > 편집 > 결과값 복사) 기능 검증.

사용자 요청: "결과값 복사 — 블록을 선택하고 단축키(또는 메뉴)를 누르면
계산된 값만 텍스트로 OS 클립보드에 복사되는 기능. 보고서나 다른 문서에
숫자만 옮겨 붙일 때 편합니다."

tests/conftest.py의 autouse fixture(isolated_clipboard)가 QApplication.clipboard()를
가짜로 돌려두므로, 실제 OS 클립보드는 전혀 건드리지 않는다.
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


def _evaluated_block(text: str, scope: Scope | None = None) -> MathBlock:
    block = MathBlock(position=(0, 0))
    block.set_input_text(text)
    block.evaluate(scope if scope is not None else Scope())
    return block


# --- MathBlock.result_value_text() ---


def test_result_value_text_for_plain_expression():
    scope = Scope()
    _evaluated_block("A = 5m", scope)
    _evaluated_block("B = 10m", scope)
    q = _evaluated_block("Q = A + B", scope)
    assert q.result_value_text() == "15 m"


def test_result_value_text_returns_value_even_when_input_already_shows_it():
    """"a = 100"처럼 화면 결과 줄은 안 보여도(_result_line_text()==None), 값 자체는 돌려줘야 한다."""
    block = _evaluated_block("a = 100")
    assert block._result_line_text() is None
    assert block.result_value_text() == "100"


def test_result_value_text_is_none_for_error_block():
    block = _evaluated_block("a = 100mpa")  # 단위 대소문자 오타로 에러
    assert block.result().is_error
    assert block.result_value_text() is None


def test_result_value_text_is_none_before_evaluation():
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    assert block.result_value_text() is None


def test_result_value_text_respects_preferred_unit():
    block = _evaluated_block("d = 5m")
    block.set_preferred_unit("mm")
    assert block.result_value_text() == "5000 mm"


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


def test_copy_result_value_puts_value_on_clipboard(window, isolated_clipboard):
    scope = Scope()
    block = MathBlock(position=(0, 0))
    block.set_input_text("F = 200 kN")
    window._scene.addItem(block)
    block.evaluate(scope)
    block.setSelected(True)

    window._on_copy_result_value()

    assert isolated_clipboard.text() == "200 kN"


def test_copy_result_value_with_multiple_selected_joins_in_screen_order(window, isolated_clipboard):
    scope = Scope()
    top = MathBlock(position=(0, 0))
    top.set_input_text("A = 5m")
    window._scene.addItem(top)
    top.evaluate(scope)

    bottom = MathBlock(position=(0, 100))
    bottom.set_input_text("B = 10m")
    window._scene.addItem(bottom)
    bottom.evaluate(scope)

    # 일부러 선택 순서를 반대로 해도 화면 위->아래 순서로 나와야 한다.
    bottom.setSelected(True)
    top.setSelected(True)

    window._on_copy_result_value()

    assert isolated_clipboard.text() == "5 m\n10 m"


def test_copy_result_value_skips_error_and_non_math_blocks(window, isolated_clipboard):
    scope = Scope()
    good = MathBlock(position=(0, 0))
    good.set_input_text("A = 5m")
    window._scene.addItem(good)
    good.evaluate(scope)

    error_block = MathBlock(position=(0, 100))
    error_block.set_input_text("B = 100mpa")
    window._scene.addItem(error_block)
    error_block.evaluate(scope)

    text_block = TextBlock(position=(0, 200))
    text_block.set_text("설명")
    window._scene.addItem(text_block)

    for block in (good, error_block, text_block):
        block.setSelected(True)

    window._on_copy_result_value()

    assert isolated_clipboard.text() == "5 m"


def test_copy_result_value_with_nothing_useful_selected_does_not_touch_clipboard(window, isolated_clipboard):
    text_block = TextBlock(position=(0, 0))
    text_block.set_text("설명")
    window._scene.addItem(text_block)
    text_block.setSelected(True)

    window._on_copy_result_value()

    assert isolated_clipboard.text() == ""


def test_copy_result_action_enabled_only_with_valid_math_result_selected(window):
    window._update_edit_menu_state()
    assert not window._copy_result_action.isEnabled()

    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    block.evaluate(Scope())
    block.setSelected(True)
    window._update_edit_menu_state()

    assert window._copy_result_action.isEnabled()


def test_copy_result_value_ignored_while_editing_text(window, isolated_clipboard):
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    block.evaluate(Scope())
    block.setSelected(True)
    block.start_editing()
    _app.processEvents()

    window._on_copy_result_value()

    assert isolated_clipboard.text() == ""

    block.finish_editing()
