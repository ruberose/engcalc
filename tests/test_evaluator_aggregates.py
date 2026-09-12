"""engine/functions.py의 목록(리스트) 집계 함수(sum/max/min/avg/count) 단위 테스트."""

from engine.evaluator import evaluate
from engine.scope import Scope


def test_list_literal_assignment():
    """"[10, 20, 30]" 같은 목록 리터럴을 변수에 대입할 수 있어야 한다."""
    scope = Scope()
    result = evaluate("loads = [10, 20, 30]", scope)
    assert not result.is_error
    assert [float(v) for v in scope.get("loads")] == [10.0, 20.0, 30.0]


def test_sum_of_plain_numbers():
    """단위 없는 숫자 목록의 합."""
    scope = Scope()
    evaluate("loads = [10, 20, 30]", scope)
    result = evaluate("sum(loads)", scope)
    assert not result.is_error
    assert float(result.value) == 60.0


def test_max_and_min_of_plain_numbers():
    """단위 없는 숫자 목록의 최댓값/최솟값."""
    scope = Scope()
    evaluate("loads = [10, 30, 20]", scope)
    max_result = evaluate("max(loads)", scope)
    min_result = evaluate("min(loads)", scope)
    assert float(max_result.value) == 30.0
    assert float(min_result.value) == 10.0


def test_avg_of_plain_numbers():
    """단위 없는 숫자 목록의 평균."""
    scope = Scope()
    evaluate("loads = [10, 20, 30]", scope)
    result = evaluate("avg(loads)", scope)
    assert not result.is_error
    assert float(result.value) == 20.0


def test_count_of_list():
    """목록의 항목 개수."""
    scope = Scope()
    evaluate("loads = [10, 20, 30]", scope)
    result = evaluate("count(loads)", scope)
    assert not result.is_error
    assert float(result.value) == 3.0


def test_aggregate_functions_with_units():
    """단위가 붙은 값(예: 여러 하중 케이스의 kN)의 목록도 집계할 수 있어야 한다 (계획서 5.2 관련 실무 사례)."""
    scope = Scope()
    evaluate("loads = [10 kN, 20 kN, 30 kN]", scope)
    total = evaluate("sum(loads)", scope)
    biggest = evaluate("max(loads)", scope)
    assert not total.is_error
    assert not biggest.is_error
    assert abs(total.value.to("kN").magnitude - 60.0) < 1e-9
    assert abs(biggest.value.to("kN").magnitude - 30.0) < 1e-9


def test_mean_is_an_alias_for_avg():
    """mean과 avg는 같은 결과를 내는 별칭이어야 한다."""
    scope = Scope()
    evaluate("loads = [10, 20, 30]", scope)
    avg_result = evaluate("avg(loads)", scope)
    mean_result = evaluate("mean(loads)", scope)
    assert float(avg_result.value) == float(mean_result.value)


def test_aggregate_of_empty_list_is_an_error_for_max_min_avg():
    """빈 목록의 최댓값/최솟값/평균은 의미가 없으므로 앱이 죽지 않고 에러여야 한다."""
    scope = Scope()
    evaluate("empty_list = []", scope)
    assert evaluate("max(empty_list)", scope).is_error
    assert evaluate("min(empty_list)", scope).is_error
    assert evaluate("avg(empty_list)", scope).is_error


def test_sum_and_count_of_empty_list_are_zero():
    """빈 목록의 합/개수는 에러가 아니라 0이어야 한다."""
    scope = Scope()
    evaluate("empty_list = []", scope)
    assert float(evaluate("sum(empty_list)", scope).value) == 0.0
    assert float(evaluate("count(empty_list)", scope).value) == 0.0


def test_max_of_incompatible_units_is_an_error():
    """서로 다른 물리량(예: 길이와 힘)이 섞인 목록의 최댓값은 에러여야 한다."""
    scope = Scope()
    evaluate("mixed = [10 kN, 5 mm]", scope)
    result = evaluate("max(mixed)", scope)
    assert result.is_error
