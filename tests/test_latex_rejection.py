"""
LaTeX 문법(백슬래시 명령어, 중괄호 그룹핑)을 아예 지원하지 않는지 검증.

사용자 요청: "라텍스 문법은 아예 고려하지 말고 사용하자. 헷갈리지 않도록
아예 없애버리는게 낫겠어."

배경: "sigma_{allow}"처럼 중괄호로 묶은 아래첨자는 mathtext가 예쁘게
렌더링은 해주지만, 실제 계산 엔진(SymPy의 Python식 파서)은 이 문법을
이해하지 못해 항상 에러가 났다 — "화면엔 되는 것처럼 보이는데 계산은
안 되는" 혼란스러운 상태였다. 이제는 백슬래시/중괄호가 섞인 입력은
렌더링도 포기하고(원문 그대로 표시), 에러 메시지도 명확하게
"LaTeX 문법은 지원하지 않는다"고 안내한다.
"""

from PySide6.QtWidgets import QApplication

from engine.evaluator import evaluate
from engine.scope import Scope
from rendering.math_renderer import render_to_pixmap

_app = QApplication.instance() or QApplication([])


def test_backslash_latex_command_fails_with_clear_message():
    """"\\sqrt{x}"처럼 백슬래시 LaTeX 명령어는 명확한 안내 메시지로 실패해야 한다."""
    result = evaluate(r"\sqrt{x}", Scope())
    assert result.is_error
    assert "LaTeX" in result.error
    assert "sqrt(x)" in result.error  # 대신 써야 할 문법을 안내


def test_brace_grouping_fails_even_without_backslash():
    """
    "sigma_{allow}"처럼 백슬래시는 없어도 중괄호 그룹핑만으로도 실패해야 한다.

    버그 재현: 이전엔 mathtext가 예쁘게 그려줘서(화면엔 정상으로 보임)
    실제로는 계산이 안 되는 걸 사용자가 알아채기 어려웠다.
    """
    result = evaluate("sigma_{allow} = 24", Scope())
    assert result.is_error
    assert "LaTeX" in result.error


def test_curly_brace_exponent_fails_with_clear_message_not_cryptic_typeerror():
    """
    "x^{10}"은 예전엔 '{10}'을 파이썬 집합(set) 리터럴로 잘못 해석해서
    "unsupported operand type(s) for ** or pow()" 같은 알 수 없는 에러가
    났었다. 이제는 미리 걸러서 명확한 LaTeX 안내 메시지를 보여줘야 한다.
    """
    result = evaluate("x^{10}", Scope())
    assert result.is_error
    assert "LaTeX" in result.error
    assert "set" not in result.error  # 예전의 알 수 없는 파이썬 내부 에러가 아님


def test_render_to_pixmap_gives_up_on_backslash():
    """렌더링도 백슬래시가 있으면 mathtext로 예쁘게 그리지 않고 포기해야 한다(빈 QPixmap)."""
    assert render_to_pixmap(r"\frac{a}{b}", 14).isNull()


def test_render_to_pixmap_gives_up_on_curly_braces():
    """중괄호만 있어도(백슬래시 없어도) 렌더링을 포기해야 한다."""
    assert render_to_pixmap("sigma_{allow}", 14).isNull()
    assert render_to_pixmap("x^{10}", 14).isNull()


def test_plain_bare_subscript_still_works_normally():
    """
    중괄호 없는 단일 문자 아래/위첨자("F_y", "x^2")는 여전히 정상 동작해야 한다
    (LaTeX 관련 변경으로 이 기존 기능까지 망가지면 안 됨).
    """
    render_pixmap = render_to_pixmap("F_y", 14)
    assert not render_pixmap.isNull()

    result = evaluate("F_y = 300", Scope())
    assert not result.is_error
    assert float(result.value) == 300.0
    assert result.variable_name == "F_y"


def test_normal_expression_without_latex_chars_unaffected():
    """LaTeX 문자가 전혀 없는 평범한 수식은 그대로 잘 계산되어야 한다."""
    result = evaluate("a = 5 * 2", Scope())
    assert not result.is_error
    assert float(result.value) == 10.0
