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
from engine.parser import ParsedInput, parse_input
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


class UserFunction:
    """
    "f(x) = x^2 + 1" 같은 사용자 정의 함수 — scope에 등록되어 "f(5)"처럼 호출된다.

    정의된 시점의 scope(그 위 블록들이 채워둔 변수값)를 그대로 복사해서 갖고
    있다가("클로저"), 실제 호출될 때마다 매개변수 자리에 인자값을 채운
    scope로 engine.evaluator.evaluate()를 다시 돌려서 계산한다.

    Note:
        SymPy의 Lambda(심볼릭 함수)를 쓰지 않는 이유: 매개변수를 SymPy
        심볼(Symbol)로 두고 본문에 단위 있는 값(Pint Quantity)이 섞이면(예:
        "x + 5mm"), SymPy가 심볼과 함께 식을 만들면서 Quantity를 억지로
        숫자로 바꾸려다 예외를 던진다(심볼과 Quantity는 SymPy 식 안에서
        같이 있을 수 없음). 여기서는 호출 시점에 매개변수를 항상 "이미 계산된
        구체적인 값"(숫자 또는 Quantity)으로 바로 대입해 evaluate()를 다시
        타므로, 보통 수식 블록이 계산되는 경로와 완전히 같아서 이 문제가
        생기지 않는다.
    """

    #: 함수가 자기 자신을(또는 서로를) 무한히 호출하는 실수를 했을 때 파이썬
    #: RecursionError로 프로그램이 죽기 전에 먼저 걸러내기 위한 호출 깊이 제한.
    _MAX_CALL_DEPTH = 50

    def __init__(self, name: str, params: list[str], body_text: str, captured_scope: dict[str, Any]) -> None:
        self.name = name
        self.params = params
        self.body_text = body_text
        self.captured_scope = captured_scope
        self._call_depth = 0

    def __call__(self, *args: Any) -> Any:
        if len(args) != len(self.params):
            raise TypeError(f"{self.name}() 함수는 인자 {len(self.params)}개가 필요합니다(받은 값: {len(args)}개)")

        if self._call_depth >= self._MAX_CALL_DEPTH:
            raise RecursionError(f"{self.name}() 함수 호출이 너무 깊습니다 (재귀 호출을 확인하세요)")

        call_scope = Scope()
        for key, value in self.captured_scope.items():
            call_scope.set(key, value)
        for param_name, arg_value in zip(self.params, args):
            call_scope.set(param_name, arg_value)

        self._call_depth += 1
        try:
            result = evaluate(self.body_text, call_scope)
        finally:
            self._call_depth -= 1

        if result.is_error:
            raise ValueError(f"{self.name}() 함수 오류: {result.error}")
        if result.value is None:
            raise ValueError(f"{self.name}() 함수의 본문이 비어 있습니다")
        return result.value


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

    if parsed.function_params is not None:
        return _define_function(parsed, scope)

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

    if isinstance(value, sympy.Basic):
        undefined_names = _undefined_names_in(value)
        if undefined_names:
            return EvalResult(variable_name=parsed.variable_name, error=f"정의되지 않은 변수: {', '.join(undefined_names)}")

    if _is_invalid_numeric_result(value):
        return EvalResult(variable_name=parsed.variable_name, error="계산 오류: 0으로 나누거나 정의되지 않은 값입니다 (무한대/nan)")

    if parsed.variable_name is not None:
        scope.set(parsed.variable_name, value)

    return EvalResult(value=value, variable_name=parsed.variable_name)


def _undefined_names_in(value: sympy.Basic) -> list[str]:
    """
    계산 결과에 아직 남아있는 "정의되지 않은 이름"을 모두 모아 정렬해서 돌려준다.

    두 가지 형태로 남을 수 있다:
    - 자유 변수(Symbol) — 예: "b * 2"에서 b를 정의한 적이 없는 경우.
    - 정의되지 않은 함수 호출(SymPy의 AppliedUndef) — 예를 들어 함수 이름을
      "stres(F, A)"처럼 잘못 타이핑하면, SymPy는 에러를 내는 대신 조용히
      "정의되지 않은 함수를 부르는 식"으로 만들어버린다(호출 문법 자체는
      문제가 없어서). 그대로 두면 오타 난 함수 호출이 에러 없이 결과처럼
      보이는 위험한 상태가 되므로, 자유 변수와 똑같이 잡아낸다.
    """
    names = {str(symbol) for symbol in value.free_symbols}
    names |= {str(call.func) for call in value.atoms(sympy.core.function.AppliedUndef)}
    return sorted(names)


def _define_function(parsed: ParsedInput, scope: Scope) -> EvalResult:
    """
    "f(x) = x^2 + 1" 같은 함수 정의 한 줄을 처리한다.

    Note:
        가능하면 본문에서 정의되지 않은 변수를 미리 잡아내지만(_validate_function_body),
        단위가 섞여 있으면 미리 판단할 수 없어 조용히 넘어간다 — 그런 경우는
        UserFunction이 실제로 호출될 때 evaluate()가 대신 검증해준다.

        정의 자체는 (변수 대입처럼) 화면에 따로 보여줄 값이 없으므로
        EvalResult.value는 항상 None — MathBlock은 이미 "값이 없으면 입력
        원문만 보여준다"는 규칙이 있어서 그대로 "f(x) = x^2 + 1"처럼 입력한
        그대로 표시된다.
    """
    params = parsed.function_params
    assert params is not None  # 이 함수를 부르는 evaluate()가 이미 확인함

    undefined_names = _validate_function_body(parsed.expression_text, params, scope)
    if undefined_names:
        return EvalResult(variable_name=parsed.variable_name, error=f"정의되지 않은 변수: {', '.join(sorted(undefined_names))}")

    function = UserFunction(
        name=parsed.variable_name,
        params=params,
        body_text=parsed.expression_text,
        captured_scope=scope.as_dict(),
    )
    scope.set(parsed.variable_name, function)
    return EvalResult(variable_name=parsed.variable_name)


def _validate_function_body(expression_text: str, params: list[str], scope: Scope) -> set[str] | None:
    """
    가능하면 함수 본문에서 매개변수도 아니고 이전 블록에서 정의된 것도 아닌
    "정의되지 않은 변수"를 미리 찾아낸다.

    매개변수 이름 자리에 실제 값 대신 SymPy 심볼(Symbol)을 넣어 한 번
    파싱해보는 방식이다. 본문에 단위 있는 값(Pint Quantity)이 함께 있으면
    (예: "x + 5mm") 심볼과 Quantity를 같은 식에 놓으려다 SymPy/Pint가
    예외를 던지는데(심볼은 아직 "구체적인 값"이 아니라서), 이건 실제 오류가
    아니라 "미리 판단할 수 없다"는 뜻이므로 조용히 None을 돌려주고 넘어간다
    — 함수가 실제로 호출될 때는 매개변수 자리에 심볼이 아니라 진짜 값이
    들어가므로 이 문제 자체가 생기지 않는다(UserFunction 참고).

    Returns:
        정의되지 않은 이름(문자열)들의 집합. 미리 판단할 수 없거나 문제가 없으면 None.
    """
    try:
        param_symbols = [sympy.Symbol(name) for name in params]
        expression_text = attach_units(expression_text)
        local_dict = {
            **FUNCTIONS,
            **CONSTANTS,
            **_UNIT_LOCALS,
            **scope.as_dict(),
            **dict(zip(params, param_symbols)),
        }
        body = parse_expr(expression_text, local_dict=local_dict, transformations=_TRANSFORMATIONS)
    except Exception:  # noqa: BLE001 - 판단을 포기하고 호출 시점 검증에 맡기기 위해 광범위하게 잡음
        return None

    if not isinstance(body, sympy.Basic):
        return None

    param_names = {str(symbol) for symbol in param_symbols}
    undefined_names = set(_undefined_names_in(body)) - param_names
    return undefined_names or None


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
