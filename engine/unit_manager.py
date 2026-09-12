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

#: 단위 자동완성(blocks/unit_suggestion_popup.py)에 후보로 보여줄 단위 이름 목록.
#: Pint가 아는 단위는 SI 접두어 조합까지 합치면 수천 개라 그대로 보여주면
#: 오히려 방해가 된다 — docs/사용법.txt "지원하는 단위" 목록과 맞춰서, 이
#: 프로그램이 실제로 문서화하고 실무에서 쓸 법한 단위만 추렸다.
KNOWN_UNIT_NAMES: tuple[str, ...] = (
    # 길이
    "m", "cm", "mm", "km", "in", "ft", "yd",
    # 체적 (면적/체적은 대부분 m*m 처럼 계산으로 얻어지지만 L은 리터럴로도 씀)
    "L",
    # 힘
    "N", "kN", "MN", "kgf", "tonf", "lbf",
    # 응력
    "Pa", "kPa", "MPa", "GPa", "psi", "ksi",
    # 질량
    "kg", "g", "ton", "lb",
    # 시간
    "s", "min", "hr",
    # 온도
    "degC", "degF", "K",
    # 각도
    "deg", "rad",
)


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


# 단위 하나("kg", "m2" 처럼 글자로 시작하는 토큰)와, 그걸 *,/,거듭제곱으로 이어붙인
# 복합단위("kg/m^3", "kN*m")를 나타낸다. "*"/"/" 뒤에는 반드시 "글자로 시작하는"
# 토큰만 오도록 강제한 게 핵심이다 — 그래야 "2m*3*4kN"에서 "m" 뒤의 "*3*4kN"을
# 통째로 단위로 삼키려다 실패하는 일이 없다("m*3"은 시작하는 숫자 "3"에서 바로
# 끊기고, "m"만 단위 후보로 남는다).
_UNIT_WORD = r"[A-Za-z][A-Za-z0-9]*"
_UNIT_EXPR = rf"{_UNIT_WORD}(?:\^\d+)?(?:[*/]{_UNIT_WORD}(?:\^\d+)?)*"

# 숫자 뒤에 (공백이 있든 없든) 오는 "단위처럼 생긴" 토큰을 찾는다.
# 예: "200 kN", "32mm"(공백 없이 붙여 써도 인식), "5 kg/m^3", "2m*3*4kN"(m만 단위로 잡음)
# 앞쪽 lookbehind는 "sigma1 200mm"처럼 다른 식별자 중간의 숫자를 잘못 잡지 않기 위함.
# 뒤에 오는 토큰이 진짜 단위인지는 is_valid_unit()으로 한 번 더 검증하므로,
# 공백을 선택적으로(0개 이상) 허용해도 "1e5"(과학적 표기) 같은 숫자는
# 후보 단위 "e5"가 실제 단위가 아니라서 안전하게 원래 형태로 남는다.
_UNIT_SUFFIX_PATTERN = re.compile(rf"(?<![A-Za-z0-9_.])(\d+(?:\.\d+)?)[ \t]*({_UNIT_EXPR})")


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


# 단위 하나 또는 "*"/"/" 토큰을 순서대로 뽑아낸다. format_unit_expression()에서
# 사용자가 입력한 순서를 그대로 지키면서 각 조각만 예쁜 기호로 바꾸는 데 쓴다.
_UNIT_TOKEN_PATTERN = re.compile(r"([*/])|([A-Za-z][A-Za-z0-9]*(?:\^\d+)?)")


def format_unit_expression(unit_text: str) -> str:
    """
    단위 문자열(예: "tonf*m")을 사용자가 쓴 순서 그대로 지키면서 Pint의 예쁜
    기호(예: "tf·m")로 바꾼다.

    Args:
        unit_text: "tonf*m", "kg/m^3" 같은 단위 문자열

    Returns:
        각 조각을 개별적으로 Pint 기호로 바꿔 원래 순서대로 이어붙인 문자열.
        알 수 없는 조각은 원래 글자 그대로 남긴다.

    Note:
        Pint의 기본 포맷터(~P)는 복합 단위를 통째로 넘기면 내부 정렬 규칙대로
        재배열해서 보여준다 — "tonf*m"이라고 입력해도 결과가 "m·tf"로 앞뒤가
        뒤바뀌어 나오는 문제가 있었다(버그 리포트로 발견). 전체를 한 번에
        포맷하는 대신 토큰(단위/연산자) 단위로 쪼개 각각 따로 포맷한 뒤 원래
        순서로 다시 이어붙이면 이 문제를 피할 수 있다.
    """
    parts: list[str] = []
    for operator, unit_word in _UNIT_TOKEN_PATTERN.findall(unit_text):
        if operator:
            parts.append("·" if operator == "*" else operator)
            continue
        try:
            parts.append(f"{ureg.parse_units(unit_word):~P}")
        except Exception:  # noqa: BLE001 - 알 수 없는 조각은 원래 글자 그대로 보여줌
            parts.append(unit_word)
    return "".join(parts)
