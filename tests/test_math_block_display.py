"""blocks/math_block.py의 결과 줄 표시(중복 방지) 로직 단위 테스트."""

from PySide6.QtWidgets import QApplication

from blocks.math_block import MathBlock
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


def _evaluated_block(text: str, scope: Scope | None = None) -> MathBlock:
    block = MathBlock(position=(0, 0))
    block.set_input_text(text)
    block.evaluate(scope if scope is not None else Scope())
    return block


def test_literal_assignment_with_space_has_no_duplicate_result_line():
    """"a = 100"처럼 입력이 이미 값을 담고 있으면 결과 줄을 또 표시하지 않는다."""
    block = _evaluated_block("a = 100")
    assert block._result_line_text() is None


def test_literal_unit_assignment_without_space_has_no_duplicate_result_line():
    """
    버그체크 중 발견: "A = 5M"처럼 숫자와 단위를 붙여 쓰면, format_value()가
    항상 "5 M"(공백 있음)로 포맷해서 문자열이 정확히 안 맞아 중복 표시가 샜다.
    ("M"은 Pint 기본 단위 "molar"라서 유효한 단위로 인식됨.)
    """
    block = _evaluated_block("A = 5M")
    assert block._result_line_text() is None, "공백 차이 때문에 중복된 결과 줄이 표시됨"


def test_expression_referencing_variables_still_shows_result_line():
    """"Q = A + B"처럼 입력 자체에 값이 없는 경우엔 결과 줄이 정상적으로 떠야 한다(중복 아님)."""
    scope = Scope()
    _evaluated_block("A = 5M", scope)
    _evaluated_block("B = 10M", scope)
    q_block = _evaluated_block("Q = A + B", scope)
    assert q_block._result_line_text() == "= 15 M"


def test_plain_expression_without_assignment_shows_result_line():
    """대입이 아닌 순수 계산식(예: "a * 2")은 입력에 값이 없으니 결과 줄이 떠야 한다."""
    scope = Scope()
    _evaluated_block("a = 100", scope)
    block = _evaluated_block("a * 2", scope)
    assert block._result_line_text() == "= 200"


def test_trailing_calculator_equals_is_stripped_from_displayed_input():
    """
    버그체크 중 발견: "A + B ="처럼 계산기 습관으로 끝에 "="를 붙이면, 계산에서는
    무시되지만 화면에 표시되는 입력 원문에는 그 "="가 그대로 남아있었다. 그러면
    입력 줄 끝의 "="와 그 아래 결과 줄("= 15m")의 "="가 겹쳐 보여서 등호가 두 번
    있는 것처럼 보였다. 화면에 표시할 self._input_text 자체에서도 지워야 한다.
    """
    scope = Scope()
    _evaluated_block("A = 5m", scope)
    _evaluated_block("B = 10m", scope)
    block = _evaluated_block("A + B =", scope)

    assert block.input_text() == "A + B", "표시되는 입력 텍스트에 trailing '='가 남아있음"
    assert block._result_line_text() == "= 15 m"


def test_trailing_calculator_equals_stripped_even_without_trailing_space():
    """"a = 100=" 처럼 공백 없이 붙은 trailing "="도 표시 텍스트에서 지워져야 한다."""
    block = _evaluated_block("a = 100=")
    assert block.input_text() == "a = 100"


def test_real_comparison_operator_is_not_affected_by_trailing_strip():
    """">=" 같은 진짜 비교 연산자는 trailing "=" 제거 로직에 영향받으면 안 된다."""
    block = _evaluated_block("a >=")
    assert block.input_text() == "a >="
