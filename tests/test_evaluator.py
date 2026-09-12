"""engine/evaluator.py 단위 테스트."""

from engine.evaluator import evaluate
from engine.scope import Scope


def test_variable_assignment_updates_scope():
    """'a = 100'을 계산하면 scope에 a=100이 등록되어야 한다."""
    scope = Scope()
    result = evaluate("a = 100", scope)
    assert not result.is_error
    # SymPy Float를 파이썬 int와 '=='로 바로 비교하면 정밀도 차이로 False가 나올 수 있어
    # float()로 변환해서 비교한다.
    assert float(scope.get("a")) == 100.0
    assert float(result.value) == 100.0


def test_reference_previous_variable():
    """이전 블록에서 정의한 변수를 다음 수식에서 그대로 쓸 수 있어야 한다."""
    scope = Scope()
    evaluate("a = 100", scope)
    result = evaluate("a * 2", scope)
    assert not result.is_error
    assert float(result.value) == 200.0


def test_undefined_variable_is_reported_as_error():
    """정의되지 않은 변수를 쓰면 앱이 죽지 않고 에러 메시지로 돌아와야 한다."""
    scope = Scope()
    result = evaluate("b * 2", scope)
    assert result.is_error


def test_degree_based_trig_function():
    """sin(30)은 구조설계 관례대로 '30도'의 사인값(0.5)이어야 한다 (계획서 5.2)."""
    scope = Scope()
    result = evaluate("sin(30)", scope)
    assert not result.is_error
    assert abs(float(result.value) - 0.5) < 1e-9


def test_comparison_operator():
    """'<' 비교는 두 변수 값을 채운 뒤 True/False로 계산되어야 한다."""
    scope = Scope()
    evaluate("sigma = 10", scope)
    evaluate("sigma_허용 = 24", scope)
    result = evaluate("sigma < sigma_허용", scope)
    assert not result.is_error
    assert result.value is True


def test_power_operator():
    """'^'는 거듭제곱으로 해석되어야 한다 (SymPy 기본값인 XOR이 아님)."""
    scope = Scope()
    result = evaluate("2^10", scope)
    assert not result.is_error
    assert float(result.value) == 1024.0


def test_empty_expression_has_no_error():
    """빈 입력(방금 만든 블록)은 에러가 아니라 '아직 계산 전' 상태여야 한다."""
    scope = Scope()
    result = evaluate("", scope)
    assert not result.is_error
    assert result.value is None


def test_division_by_zero_is_an_error_not_silent_infinity():
    """
    '1/0'은 SymPy에서 예외 없이 zoo(복소무한대)를 돌려주는데, 이걸 '정상 결과'
    처럼 scope에 남겨두면 분모가 실수로 0이 된 경우를 사용자가 못 알아채고
    잘못된 계산이 뒤로 계속 퍼질 수 있다. 공학 계산 도구이므로 반드시 에러여야 한다.
    """
    scope = Scope()
    result = evaluate("a = 1/0", scope)
    assert result.is_error
    assert not scope.has("a"), "0으로 나눈 결과가 그대로 scope에 등록되면 안 됨"


def test_zero_divided_by_zero_is_an_error():
    """'0/0'(SymPy에서 nan)도 마찬가지로 에러 처리되어야 한다."""
    scope = Scope()
    result = evaluate("0/0", scope)
    assert result.is_error


def test_division_by_zero_does_not_propagate_through_scope():
    """0으로 나눈 값이 scope에 안 남으므로, 그걸 참조하는 다음 블록은 '정의되지 않은 변수' 에러가 나야 한다."""
    scope = Scope()
    evaluate("a = 1/0", scope)
    result = evaluate("b = a + 5", scope)
    assert result.is_error


def test_division_by_zero_with_units_is_an_error():
    """단위가 붙은 값을 0으로 나눠도(Quantity로 감싸진 zoo) 에러여야 한다."""
    scope = Scope()
    evaluate("F = 200 kN", scope)
    result = evaluate("a = F / 0", scope)
    assert result.is_error


def test_calling_undefined_name_as_function_is_reported_as_error():
    """
    정의된 적 없는 이름을 함수처럼(괄호와 함께) 부르면 에러여야 한다.

    SymPy 파서는 이런 호출을 예외 없이 "정의되지 않은 함수 호출" 심볼로
    조용히 만들어버리는데, 그대로 두면 함수 이름 오타가 에러 표시 없이
    결과처럼 보이는 위험한 상태가 된다 — 괄호 없는 정의되지 않은 변수와
    똑같이 취급해야 한다.
    """
    scope = Scope()
    result = evaluate("totallyUndefinedFunc(5)", scope)
    assert result.is_error


def test_normal_division_with_units_still_works():
    """0으로 나누기 방지 로직을 추가해도, 정상적인 단위 나눗셈은 그대로 동작해야 한다."""
    scope = Scope()
    evaluate("F = 200 kN", scope)
    result = evaluate("a = F / 4", scope)
    assert not result.is_error
    assert abs(result.value.to("kN").magnitude - 50.0) < 1e-9
