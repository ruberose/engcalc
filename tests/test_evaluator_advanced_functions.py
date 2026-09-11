"""
공식 FUNCTIONS 목록(engine/functions.py)에는 없지만, SymPy 파서의 기본
global_dict가 새어나와서 실제로 동작하는 고급 함수들을 검증한다.

사용자 질문: "미적분이나 무한급수 등 고급 수학 기법도 계산되나?"
직접 evaluate()를 돌려 확인한 결과를 그대로 회귀 테스트로 남겨둔다 — 이건
"의도적으로 설계된 기능"이 아니라 parse_expr()이 local_dict에 없는 이름을
SymPy 기본 이름공간에서 찾아주는 부수 효과라서, 나중에 engine/evaluator.py의
파서 설정이 바뀌면 조용히 사라질 수 있다. 그때 이 테스트가 먼저 깨져서
알려주는 역할을 한다.

핵심 규칙: 결과에 변수가 그대로 남는("기호식") 계산은 evaluate()가
"정의되지 않은 변수" 에러로 처리한다 — 숫자 하나로 완전히 떨어지는 결과만
화면에 보여줄 수 있다.
"""

from PySide6.QtWidgets import QApplication

from engine.evaluator import evaluate
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


def test_limit_to_concrete_point_works():
    """극한: 특정 점으로 수렴하는 극한은 숫자로 떨어지므로 계산된다."""
    result = evaluate("limit(1/x, x, oo)", Scope())
    assert not result.is_error
    assert float(result.value) == 0.0


def test_solve_equation_works():
    """방정식 풀이: 해가 숫자 리스트로 나오므로 계산된다."""
    result = evaluate("solve(x^2 - 4, x)", Scope())
    assert not result.is_error
    assert sorted(float(v) for v in result.value) == [-2.0, 2.0]


def test_definite_integral_works():
    """정적분(구간 지정): 결과가 숫자로 떨어지므로 계산된다."""
    result = evaluate("integrate(x^2, (x, 0, 2))", Scope())
    assert not result.is_error
    assert abs(float(result.value) - 8 / 3) < 1e-9


def test_infinite_series_sum_works():
    """무한급수 합: 수렴하는 급수는 숫자로 떨어지므로 계산된다 (바젤 문제: pi^2/6)."""
    result = evaluate("Sum(1/n^2, (n, 1, oo))", Scope())
    assert not result.is_error
    assert abs(float(result.value) - 1.644934) < 1e-5


def test_symbolic_differentiation_is_reported_as_undefined_variable():
    """
    기호 미분(diff)은 결과에 변수 x가 그대로 남아서("2*x") "정의되지 않은
    변수" 에러로 처리되어야 한다 — 계산 자체는 SymPy가 해내지만 이 앱은
    기호식 결과를 표시할 수 없다.
    """
    result = evaluate("diff(x^2, x)", Scope())
    assert result.is_error
    assert "정의되지 않은 변수" in result.error


def test_indefinite_integral_is_reported_as_undefined_variable():
    """부정적분도 결과에 변수가 남아서 diff와 같은 이유로 에러 처리된다."""
    result = evaluate("integrate(x^2, x)", Scope())
    assert result.is_error
    assert "정의되지 않은 변수" in result.error
