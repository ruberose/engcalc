"""
Pint 라이브러리 래퍼 — 단위가 붙은 수식(예: "200 kN")을 처리한다.

- 기본 Pint 레지스트리에 없는 단위(tonf)를 추가한다.
- 한국 구조설계 관례와 다른 Pint 기본값("ton" = 미국 short ton)을 바로잡는다.
- "200 kN" 같은 입력 텍스트를 SymPy 파서가 이해할 수 있는 형태로 미리 바꿔준다.
- 계산 결과 단위를 사람이 보기 좋은 형태로 정리한다(예: kN/mm^2 -> MPa).
"""

import re
from typing import Any

import pint

# on_redefinition="ignore" : 아래에서 "ton"을 한국 관례(미터톤)로 재정의하기 위해 필요.
ureg = pint.UnitRegistry(on_redefinition="ignore")

# 한국 구조설계 관례: "ton"은 미터톤(1000kg)이다.
# Pint 기본값은 미국 short ton(약 907kg)이라 그대로 두면 계산이 틀어진다.
ureg.define("ton = 1000 * kilogram = t = metric_ton_kr")
# Pint 기본 레지스트리에 없는 톤힘 (1 tonf = 9.80665 kN, 계획서 5.2).
ureg.define("tonf = 9.80665 * kilonewton = tf")

Quantity = ureg.Quantity


def make_quantity(magnitude: Any, unit_text: str) -> Quantity:
    """
    숫자와 단위 문자열로 Pint Quantity를 만든다.

    Args:
        magnitude: 수치. SymPy Integer/Float로 넘어올 수 있어 float()으로 정규화한다
                   (Pint는 순수 파이썬 숫자를 기대하기 때문).
        unit_text: "kN", "mm^2", "kg/m^3" 같은 단위 문자열.
    """
    return ureg.Quantity(float(magnitude), unit_text)


def is_valid_unit(unit_text: str) -> bool:
    """주어진 문자열이 Pint가 이해할 수 있는 단위 표현인지 확인한다."""
    try:
        ureg.parse_units(unit_text)
        return True
    except Exception:  # noqa: BLE001 - "일단 시도해보고" 단위인지 판단하는 용도라 광범위하게 잡음
        return False


# 숫자 뒤에 (공백이 있든 없든) 오는 "단위처럼 생긴" 토큰을 찾는다.
# 예: "200 kN", "32mm"(공백 없이 붙여 써도 인식), "5 kg/m^3"
# 앞쪽 lookbehind는 "sigma1 200mm"처럼 다른 식별자 중간의 숫자를 잘못 잡지 않기 위함.
# 뒤에 오는 토큰이 진짜 단위인지는 is_valid_unit()으로 한 번 더 검증하므로,
# 공백을 선택적으로(0개 이상) 허용해도 "1e5"(과학적 표기) 같은 숫자는
# 후보 단위 "e5"가 실제 단위가 아니라서 안전하게 원래 형태로 남는다.
_UNIT_SUFFIX_PATTERN = re.compile(r"(?<![A-Za-z0-9_.])(\d+(?:\.\d+)?)[ \t]*([A-Za-z][A-Za-z0-9_*/^]*)")


def attach_units(text: str) -> str:
    """
    입력 문자열에서 "숫자 단위" 패턴을 찾아 make_quantity() 호출 형태로 바꾼다.

    예: "F = 200 kN"  ->  "F = __quantity__(200, 'kN')"

    이렇게 텍스트 단계에서 미리 바꿔두면, engine/evaluator.py의 SymPy 파서는
    평소처럼 연산자(+, *, <, ...)만 처리하면 되고 단위 자체를 알 필요가 없다.
    뒤에 온 토큰이 실제로 Pint가 아는 단위가 아니면(예: 어쩌다 숫자 뒤에 함수/변수
    이름이 붙은 경우) 그대로 두어 원래대로 파싱되게 한다.
    """

    def _replace(match: re.Match[str]) -> str:
        number_text, unit_text = match.group(1), match.group(2)
        if not is_valid_unit(unit_text):
            return match.group(0)
        return f"__quantity__({number_text}, {unit_text!r})"

    return _UNIT_SUFFIX_PATTERN.sub(_replace, text)


# --- 결과 단위 정리 ---
# 계산 결과가 나오면, 물리량 종류(차원)별로 "이 차원이면 이 단위 계열로 보여준다"는
# 기준 단위로 먼저 바꾼 뒤, Pint의 to_compact()로 적당한 접두어(k, M, G...)를 고른다.
# 이렇게 안 하면 kN/mm^2 같은 값이 MPa로 자동 정리되지 않고 그대로 남는다
# (Pint는 차원이 같아도 이름이 다른 단위로 자동 치환해주지 않기 때문).
_CANONICAL_UNIT_BY_DIMENSION: dict[Any, str] = {
    ureg.Quantity(1, "m").dimensionality: "m",
    ureg.Quantity(1, "m**2").dimensionality: "m**2",
    ureg.Quantity(1, "m**3").dimensionality: "m**3",
    ureg.Quantity(1, "N").dimensionality: "N",
    ureg.Quantity(1, "Pa").dimensionality: "Pa",
    ureg.Quantity(1, "N*m").dimensionality: "N*m",
    ureg.Quantity(1, "kg").dimensionality: "kg",
    ureg.Quantity(1, "s").dimensionality: "s",
    ureg.Quantity(1, "kg/m**3").dimensionality: "kg/m**3",
}

# 이 차원들은 정리 대상에서 뺀다: 온도는 오프셋 단위라 임의로 다른 단위로 바꾸면
# 의미가 달라지고(계획서 5.2), 각도(deg/rad)와 무차원 값은 이미 충분히 단순하다.
_SKIP_SIMPLIFY_DIMENSIONS = {
    ureg.Quantity(1, "degC").dimensionality,
    ureg.Quantity(1, "deg").dimensionality,  # == dimensionless
}


def simplify(quantity: Quantity) -> Quantity:
    """
    계산 결과 Quantity를 사람이 보기 좋은 단위로 정리한다.

    Args:
        quantity: 임의의 연산 결과 (예: 200kN / (300mm*500mm))

    Returns:
        알려진 물리량이면 해당 계열의 기준 단위로 변환 후 적당한 접두어를 고른
        Quantity. 알 수 없는 조합이면 Pint의 to_compact() 결과를 그대로 돌려준다.
    """
    dim = quantity.dimensionality
    if dim in _SKIP_SIMPLIFY_DIMENSIONS:
        return quantity

    canonical = _CANONICAL_UNIT_BY_DIMENSION.get(dim)
    if canonical is not None:
        quantity = quantity.to(canonical)

    return quantity.to_compact()
