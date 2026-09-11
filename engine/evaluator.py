"""
수식 문자열을 계산하는 SymPy 래퍼.

engine/parser.py가 나눠준 (변수명, 수식 텍스트)를 받아 SymPy로 계산하고,
성공하면 값을, 실패하면 사람이 읽을 수 있는 에러 메시지를 돌려준다.

이 모듈은 GUI를 전혀 알지 못한다 — 터미널에서
`python -c "from engine.evaluator import evaluate; from engine.scope import Scope; ..."`
형태로 GUI 없이 단독 실행·테스트할 수 있어야 한다 (모듈 분리 원칙 1번).
"""

from dataclasses import dataclass
from typing import Any

import sympy
from sympy.parsing.sympy_parser import (
    convert_equals_signs,
    convert_xor,
    parse_expr,
    standard_transformations,
)

from engine.functions import CONSTANTS, FUNCTIONS
from engine.parser import parse_input
from engine.scope import Scope
from engine.unit_manager import Quantity, attach_units, make_quantity, simplify

# ^ 는 거듭제곱으로, ==(그리고 =)는 Eq()로 해석하도록 SymPy 기본 파서 규칙을 확장한다.
_TRANSFORMATIONS = standard_transformations + (convert_xor, convert_equals_signs)

# "200 kN" 처럼 단위가 붙은 리터럴은 attach_units()가 미리 이 이름의 호출로 바꿔둔다.
_UNIT_LOCALS = {"__quantity__": make_quantity}

# "1/0" 같은 계산은 SymPy에서 예외가 나지 않고 조용히 zoo(복소무한대)/nan/oo를
# 돌려준다. 공학 계산 도구에서 이런 값이 에러 표시 없이 "정상 결과"처럼 남아
# 이후 계산에 계속 퍼지면 위험하므로(예: 분모가 어쩌다 0이 된 실수), 명시적으로
# 에러 취급한다.
_INVALID_NUMERIC_VALUES = (sympy.zoo, sympy.nan, sympy.oo, -sympy.oo)

# 이 프로그램은 LaTeX 문법을 지원하지 않는다 — 계산 엔진(SymPy의 Python식
# 파서)은 백슬래시 명령어("\frac", "\sqrt" 등)나 중괄호 그룹핑("x^{10}")을
# 전혀 이해하지 못한다. 그냥 두면 "unexpected character after line
# continuation character" 같은 파이썬 내부 에러 메시지가 그대로 노출되거나
# ("x^{10}"처럼) 엉뚱하게 파싱되어 더 헷갈리는 에러가 나므로, 이런 문자가
# 보이면 먼저 걸러서 무엇을 대신 써야 하는지 알려준다.
_LATEX_MARKUP_CHARS = ("\\", "{", "}")
_LATEX_NOT_SUPPORTED_MESSAGE = (
    "LaTeX 문법(\\, {, })은 지원하지 않습니다. "
    "예: \\sqrt{x} 대신 sqrt(x), \\frac{a}{b} 대신 a/b, x^{10} 대신 x^10 을 사용하세요."
)


@dataclass
class EvalResult:
    """수식 한 줄을 계산한 결과."""

    value: Any = None
    variable_name: str | None = None
    error: str | None = None

    @property
    def is_error(self) -> bool:
        """계산에 실패했는지 여부."""
        return self.error is not None


def evaluate(text: str, scope: Scope) -> EvalResult:
    """
    수식 한 줄을 계산한다.

    Args:
        text: 사용자가 입력한 원본 문자열. 예: "a = 100", "a * sin(30)"
        scope: 이전 블록들에서 정의된 변수를 담고 있는 Scope.
               "a = 100" 처럼 대입문이면 계산 성공 시 이 scope에 값이 등록된다.

    Returns:
        EvalResult — 성공하면 value에 계산값이, 실패하면 error에 원인이 담긴다.
        입력이 비어 있으면 value=None, error=None인 "아직 계산 전" 상태를 돌려준다.

    Note:
        입력은 사용자가 자유롭게 타이핑한 임의의 문자열이라 어떤 예외가 날지
        미리 다 알 수 없다. 이 파싱/계산 경계에서만 폭넓게(Exception) 잡아서
        절대 앱이 죽지 않게 하고, 원인은 EvalResult.error로 전달한다.
    """
    parsed = parse_input(text)

    if not parsed.expression_text.strip():
        return EvalResult(variable_name=parsed.variable_name)

    if any(ch in parsed.expression_text for ch in _LATEX_MARKUP_CHARS):
        return EvalResult(variable_name=parsed.variable_name, error=_LATEX_NOT_SUPPORTED_MESSAGE)

    try:
        expression_text = attach_units(parsed.expression_text)
        local_dict = {**FUNCTIONS, **CONSTANTS, **_UNIT_LOCALS, **scope.as_dict()}
        raw_result = parse_expr(expression_text, local_dict=local_dict, transformations=_TRANSFORMATIONS)
    except Exception as exc:  # noqa: BLE001 - 사용자 입력 파싱 경계이므로 의도적으로 광범위하게 잡음
        return EvalResult(variable_name=parsed.variable_name, error=f"수식 오류: {exc}")

    try:
        value = _finalize(raw_result)
    except Exception as exc:  # noqa: BLE001 - 위와 동일한 이유
        return EvalResult(variable_name=parsed.variable_name, error=f"계산 오류: {exc}")

    if isinstance(value, sympy.Basic) and value.free_symbols:
        names = ", ".join(sorted(str(sym) for sym in value.free_symbols))
        return EvalResult(variable_name=parsed.variable_name, error=f"정의되지 않은 변수: {names}")

    if _is_invalid_numeric_result(value):
        return EvalResult(variable_name=parsed.variable_name, error="계산 오류: 0으로 나누거나 정의되지 않은 값입니다 (무한대/nan)")

    if parsed.variable_name is not None:
        scope.set(parsed.variable_name, value)

    return EvalResult(value=value, variable_name=parsed.variable_name)


def _finalize(raw_result: Any) -> Any:
    """
    파싱 직후 결과를 최종 표시값으로 정리한다.

    - 이미 파이썬 bool/sympy Boolean(비교 연산 결과)이면 bool로 통일.
    - 단위가 붙은 값(Pint Quantity)이면 보기 좋은 단위로 정리한다(예: kN/mm^2 -> MPa).
    - 그 외 숫자식이면 evalf()로 수치화 (변수가 남아 있으면 심볼릭 상태 그대로 반환됨).
    """
    if isinstance(raw_result, bool):
        return raw_result
    if isinstance(raw_result, sympy.logic.boolalg.BooleanAtom):
        return bool(raw_result)
    if isinstance(raw_result, Quantity):
        if _is_invalid_numeric_result(raw_result.magnitude):
            # magnitude가 zoo/nan이면 simplify()의 to_compact()가 "정의되지 않은
            # 동작" 경고를 내며 이상하게 굴 수 있으니, 정리하지 말고 그대로 반환한다
            # — evaluate()가 곧바로 이 값을 보고 에러로 처리한다.
            return raw_result
        return simplify(raw_result)
    if hasattr(raw_result, "evalf"):
        return raw_result.evalf()
    return raw_result


def _is_invalid_numeric_result(value: Any) -> bool:
    """0으로 나누기 등으로 zoo/nan/oo가 나왔는지 확인한다 (Quantity로 감싸져 있어도 확인)."""
    candidate = value.magnitude if isinstance(value, Quantity) else value
    return isinstance(candidate, sympy.Basic) and candidate in _INVALID_NUMERIC_VALUES
