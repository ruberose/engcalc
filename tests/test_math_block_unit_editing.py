"""
Ctrl+더블클릭으로 결과의 표시 단위만 바로 고치는 기능(단위 인라인 편집) 테스트.

기존에도 속성 패널의 "표시 단위" 입력으로 이 기능(set_preferred_unit)을 쓸 수
있었지만, 이번엔 블록을 직접 Ctrl+더블클릭해서 바로 단위를 바꿀 수 있게
새로 만든 진입점(start_unit_editing/finish_unit_editing)을 검증한다.
"""

from PySide6.QtWidgets import QApplication

from blocks.math_block import MathBlock
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


def _evaluated_block(text: str, scope: Scope | None = None) -> MathBlock:
    block = MathBlock(position=(0, 0))
    block.set_input_text(text)
    block.evaluate(scope if scope is not None else Scope())
    return block


def test_start_unit_editing_prefills_current_unit():
    """단위 편집을 시작하면 에디터에 지금 보이는 단위가 미리 채워져 있어야 한다."""
    block = _evaluated_block("5m + 6m")
    block.start_unit_editing()

    assert block._unit_editor is not None
    assert block._unit_editor.toPlainText() == "m"


def test_finish_unit_editing_converts_displayed_value():
    """
    사용자가 요청한 시나리오: "5m + 6m = 11m"에서 단위를 "mm"으로 바꾸면
    "5m + 6m = 11000mm"으로 자동 환산되어 보여야 한다.
    """
    block = _evaluated_block("5m + 6m")
    block.start_unit_editing()
    block._unit_editor.setPlainText("mm")
    block.finish_unit_editing()

    assert block._unit_editor is None  # 편집기는 사라져야 함
    assert block.preferred_unit() == "mm"
    assert block._combined_line_text() == "5m + 6m = 11000 mm"


def test_unit_editing_does_not_change_stored_value():
    """
    표시 단위만 바꾸는 것이므로, scope에 저장된 실제 값(다른 블록이 참조할 값)은
    바뀌면 안 된다 — 그래야 이 블록을 참조하는 다른 계산이 영향을 안 받는다.
    """
    scope = Scope()
    block = _evaluated_block("d = 5m + 6m", scope)
    original_value = block.result().value

    block.start_unit_editing()
    block._unit_editor.setPlainText("mm")
    block.finish_unit_editing()

    assert block.result().value is original_value
    assert abs(scope.get("d").to("m").magnitude - 11.0) < 1e-9


def test_unit_editing_ignored_when_no_convertible_result():
    """단위 없는 순수 숫자거나 에러 상태면 단위 편집을 시작하지 않아야 한다(바꿀 단위가 없음)."""
    plain_block = _evaluated_block("1 + 1")
    plain_block.start_unit_editing()
    assert plain_block._unit_editor is None

    error_block = _evaluated_block("b * 2")  # b가 정의 안 됨 -> 에러
    assert error_block.result().is_error
    error_block.start_unit_editing()
    assert error_block._unit_editor is None


def test_invalid_unit_input_is_ignored_gracefully():
    """말이 안 되는 단위를 입력해도 앱이 죽지 않고, 원래 값이 그대로 보여야 한다."""
    block = _evaluated_block("5m + 6m")
    block.start_unit_editing()
    block._unit_editor.setPlainText("asdf")
    block.finish_unit_editing()  # 예외를 던지면 이 테스트가 바로 실패함

    assert not block.result().is_error
    assert block._combined_line_text() == "5m + 6m = 11 m"
