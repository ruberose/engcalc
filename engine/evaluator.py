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
        return simplify(raw_result)
    if hasattr(raw_result, "evalf"):
        return raw_result.evalf()
    return raw_result
