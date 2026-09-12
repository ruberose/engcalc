"""engine/evaluator.py의 사용자 정의 함수("f(x) = ...") 단위 테스트."""

from engine.evaluator import evaluate
from engine.scope import Scope


def test_function_definition_has_no_visible_value():
    """함수 정의 자체는 (변수 대입처럼) 화면에 보여줄 결과값이 없어야 한다."""
    scope = Scope()
    result = evaluate("f(x) = x^2 + 1", scope)
    assert not result.is_error
    assert result.value is None
    assert result.variable_name == "f"


def test_single_argument_function_call():
    """정의한 함수를 다른 블록에서 호출하면 매개변수에 인자를 대입한 값이 나와야 한다."""
    scope = Scope()
    evaluate("f(x) = x^2 + 1", scope)
    result = evaluate("f(5)", scope)
    assert not result.is_error
    assert float(result.value) == 26.0


def test_multiple_argument_function_call():
    """매개변수가 여러 개인 함수도 순서대로 대입되어야 한다."""
    scope = Scope()
    evaluate("g(x, y) = x*y + 1", scope)
    result = evaluate("g(3, 4)", scope)
    assert not result.is_error
    assert float(result.value) == 13.0


def test_function_can_reference_outer_scope_variable():
    """함수 본문은 정의 시점까지 위 블록에서 채워진 변수도 참조할 수 있어야 한다."""
    scope = Scope()
    evaluate("k = 10", scope)
    evaluate("f(x) = x * k", scope)
    result = evaluate("f(3)", scope)
    assert not result.is_error
    assert float(result.value) == 30.0


def test_function_body_with_undefined_variable_is_reported_at_definition():
    """매개변수도 아니고 이전에 정의된 적도 없는 변수를 본문에 쓰면 정의 시점에 에러여야 한다."""
    scope = Scope()
    result = evaluate("h(x) = x + qqq", scope)
    assert result.is_error


def test_function_with_units_in_arguments():
    """단위가 붙은 값(Pint Quantity)을 그대로 함수 인자로 넘겨도 계산되어야 한다 (계획서 5.2 관련 실무 사례)."""
    scope = Scope()
    evaluate("stress(F, A) = F / A", scope)
    evaluate("F0 = 200 kN", scope)
    evaluate("A0 = 300 mm * 500 mm", scope)
    result = evaluate("stress(F0, A0)", scope)
    assert not result.is_error
    assert abs(result.value.to("MPa").magnitude - 1.3333333) < 1e-5


def test_calling_function_with_wrong_argument_count_is_an_error():
    """매개변수 개수와 다른 개수의 인자로 호출하면 앱이 죽지 않고 에러여야 한다."""
    scope = Scope()
    evaluate("f(x) = x", scope)
    result = evaluate("f(1, 2)", scope)
    assert result.is_error


def test_self_referential_function_call_is_an_error_not_infinite_loop():
    """자기 자신을 부르는 함수를 호출하면(정의 시점엔 자기 이름이 아직 scope에 없어 미완성 상태) 무한루프 대신 에러로 처리되어야 한다."""
    scope = Scope()
    evaluate("rec(x) = rec(x)", scope)
    result = evaluate("rec(1)", scope)
    assert result.is_error


def test_calling_undefined_name_as_function_is_an_error():
    """
    함수 이름을 잘못 타이핑해서 정의된 적 없는 이름을 함수처럼 호출하면 에러여야 한다.

    SymPy는 괄호가 붙은 미지의 이름을 조용히 "정의되지 않은 함수 호출" 심볼로
    만들어버리는데, 이걸 그대로 두면 오타가 에러 없이 결과처럼 보이는 위험한
    상태가 된다(정의되지 않은 변수를 참조했을 때와 동일하게 처리되어야 함).
    """
    scope = Scope()
    result = evaluate("totallyUndefinedFunc(5)", scope)
    assert result.is_error


def test_redefining_function_updates_scope():
    """같은 이름으로 함수를 다시 정의하면 이후 호출은 새 정의를 따라야 한다."""
    scope = Scope()
    evaluate("f(x) = x + 1", scope)
    evaluate("f(x) = x + 100", scope)
    result = evaluate("f(1)", scope)
    assert not result.is_error
    assert float(result.value) == 101.0
