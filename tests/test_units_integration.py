"""계획서 Phase 3 완료 기준 예시를 그대로 재현하는 통합 테스트."""

from engine.evaluator import evaluate
from engine.scope import Scope


def test_phase3_example_from_plan():
    """
    계획서 예시:
        F = 200 kN
        b = 300 mm
        h = 500 mm
        A = b * h                    -> 150000 mm^2
        sigma = F / A                -> 1.333 MPa
        sigma_허용 = 24 MPa
        OK = sigma < sigma_허용      -> True
    """
    scope = Scope()

    r_f = evaluate("F = 200 kN", scope)
    r_b = evaluate("b = 300 mm", scope)
    r_h = evaluate("h = 500 mm", scope)
    assert not r_f.is_error and not r_b.is_error and not r_h.is_error

    r_a = evaluate("A = b * h", scope)
    assert not r_a.is_error
    assert str(r_a.value.units) == "millimeter ** 2"
    assert abs(r_a.value.magnitude - 150000.0) < 1e-6

    r_sigma = evaluate("sigma = F / A", scope)
    assert not r_sigma.is_error
    assert str(r_sigma.value.units) == "megapascal"
    assert abs(r_sigma.value.magnitude - 1.3333333) < 1e-5

    r_allow = evaluate("sigma_허용 = 24 MPa", scope)
    assert not r_allow.is_error

    r_ok = evaluate("OK = sigma < sigma_허용", scope)
    assert not r_ok.is_error
    assert r_ok.value is True
