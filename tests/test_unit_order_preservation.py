"""
복합 단위(예: "tonf*m")를 입력했을 때 순서가 뒤바뀌지 않는지 확인.

버그 리포트: "C*D = 1.01972 m·tf" 처럼 사용자가 "tonf*m"이라고 입력해도
Pint의 기본 포맷터가 항상 정해진 순서(대략 알파벳 순)로 재배열해서
"m·tf"로 앞뒤가 바뀌어 보였다.
"""

from PySide6.QtWidgets import QApplication

from blocks.math_block import MathBlock
from engine.scope import Scope
from engine.unit_manager import format_unit_expression

_app = QApplication.instance() or QApplication([])


def test_format_unit_expression_preserves_typed_order():
    """format_unit_expression()은 입력한 순서를 그대로 지켜야 한다."""
    assert format_unit_expression("tonf*m") == "tf·m"
    assert format_unit_expression("m*tonf") == "m·tf"


def test_format_unit_expression_uses_pretty_symbols():
    """각 조각은 Pint의 짧은 기호로 바뀌어야 한다 (tonf -> tf)."""
    assert format_unit_expression("tonf") == "tf"
    assert format_unit_expression("kilonewton*meter") == "kN·m"


def test_format_unit_expression_handles_division_and_exponent():
    """나눗셈("/")과 거듭제곱("^")이 섞인 복합 단위도 순서를 지켜야 한다."""
    assert format_unit_expression("kg/m^3") == "kg/m³"


def test_math_block_result_preserves_user_typed_unit_order():
    """
    버그 리포트 재현: "C*D"의 결과를 "tonf*m"으로 표시 단위를 바꾸면,
    "m·tf"가 아니라 "tf·m"(입력한 순서 그대로)으로 보여야 한다.
    """
    scope = Scope()
    c_block = MathBlock(position=(0, 0))
    c_block.set_input_text("C = 10kN")
    c_block.evaluate(scope)

    d_block = MathBlock(position=(0, 60))
    d_block.set_input_text("D = 1m")
    d_block.evaluate(scope)

    q_block = MathBlock(position=(0, 120))
    q_block.set_input_text("C*D")
    q_block.evaluate(scope)

    q_block.set_preferred_unit("tonf*m")

    result_text = q_block._result_line_text()
    assert result_text is not None
    assert "tf·m" in result_text
    assert "m·tf" not in result_text


def test_reversed_input_order_also_preserved():
    """반대로 "m*tonf"라고 입력하면 그 순서("m·tf")가 그대로 유지되어야 한다."""
    scope = Scope()
    c_block = MathBlock(position=(0, 0))
    c_block.set_input_text("C = 10kN")
    c_block.evaluate(scope)

    d_block = MathBlock(position=(0, 60))
    d_block.set_input_text("D = 1m")
    d_block.evaluate(scope)

    q_block = MathBlock(position=(0, 120))
    q_block.set_input_text("C*D")
    q_block.evaluate(scope)

    q_block.set_preferred_unit("m*tonf")

    result_text = q_block._result_line_text()
    assert result_text is not None
    assert "m·tf" in result_text
