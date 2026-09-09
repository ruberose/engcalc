"""engine/unit_manager.py 단위 테스트."""

from engine.unit_manager import attach_units, is_valid_unit, make_quantity, simplify


def test_make_quantity_basic():
    """숫자 + 단위 문자열로 Pint Quantity가 만들어져야 한다."""
    q = make_quantity(200, "kN")
    assert q.magnitude == 200.0
    assert str(q.units) == "kilonewton"


def test_is_valid_unit():
    """실제 단위 문자열은 True, 임의의 변수/함수 이름은 False여야 한다."""
    assert is_valid_unit("kN")
    assert is_valid_unit("mm^2")
    assert is_valid_unit("kg/m^3")
    assert not is_valid_unit("sin")
    assert not is_valid_unit("asdf")


def test_attach_units_replaces_number_unit_pairs():
    """'숫자 단위' 패턴만 __quantity__() 호출로 바뀌고 나머지는 그대로여야 한다."""
    result = attach_units("F = 200 kN")
    assert result == "F = __quantity__(200, 'kN')"


def test_attach_units_ignores_non_unit_words():
    """단위가 아닌 일반 수식(예: 2 * 3)은 건드리지 않아야 한다."""
    assert attach_units("2 * 3") == "2 * 3"


def test_attach_units_without_space():
    """숫자와 단위 사이에 공백이 없어도(예: "32mm") 인식되어야 한다."""
    result = attach_units("32mm + 42mm")
    assert result == "__quantity__(32, 'mm') + __quantity__(42, 'mm')"


def test_attach_units_does_not_break_scientific_notation():
    """공백 없는 단위를 허용해도 "1e5" 같은 과학적 표기법은 건드리면 안 된다."""
    assert attach_units("a = 1e5") == "a = 1e5"


def test_korean_ton_convention():
    """한국 구조설계 관례대로 'ton'은 미터톤(1000kg)이어야 한다 (Pint 기본값인 미국 톤 아님)."""
    q = make_quantity(1, "ton")
    assert abs(q.to("kg").magnitude - 1000.0) < 1e-9


def test_tonf_custom_unit():
    """tonf(톤힘)는 9.80665 kN이어야 한다 (계획서 5.2)."""
    q = make_quantity(1, "tonf")
    assert abs(q.to("kN").magnitude - 9.80665) < 1e-6


def test_simplify_stress_to_mpa():
    """kN/mm^2 형태로 나온 응력 결과가 MPa로 자동 정리되어야 한다."""
    force = make_quantity(200, "kN")
    area = make_quantity(150000, "mm^2")
    stress = simplify(force / area)
    assert str(stress.units) == "megapascal"
    assert abs(stress.magnitude - 1.3333333) < 1e-5
