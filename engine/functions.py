"""
수식에서 쓸 수 있는 내장 함수와 상수 모음.

engine/evaluator.py가 SymPy 파서의 local_dict로 이 딕셔너리들을 넘겨줘서,
사용자가 수식에 sin(30), sqrt(2), pi 같은 이름을 그대로 쓸 수 있게 한다.

각도 함수(sin/cos/tan과 그 역함수)는 구조설계 엔지니어 관례에 따라
기본적으로 '도(degree)' 단위를 쓴다 — sin(30)은 30도의 사인값이다.
라디안 기준인 수학 표준과 다르므로 반드시 기억할 것 (계획서 5.2).
"""

from typing import Any, Callable

import sympy

# --- 각도 함수: 입력/출력 모두 degree 기준 ---
# sympy.rad()/sympy.deg()는 pi/180을 곱하고 나누는 것뿐이라 심볼릭 값에도 안전하다.


def _sin_deg(x: Any) -> Any:
    """sin(x) — x를 degree로 해석한다."""
    return sympy.sin(sympy.rad(x))


def _cos_deg(x: Any) -> Any:
    """cos(x) — x를 degree로 해석한다."""
    return sympy.cos(sympy.rad(x))


def _tan_deg(x: Any) -> Any:
    """tan(x) — x를 degree로 해석한다."""
    return sympy.tan(sympy.rad(x))


def _asin_deg(x: Any) -> Any:
    """asin(x) — 결과를 degree로 반환한다."""
    return sympy.deg(sympy.asin(x))


def _acos_deg(x: Any) -> Any:
    """acos(x) — 결과를 degree로 반환한다."""
    return sympy.deg(sympy.acos(x))


def _atan_deg(x: Any) -> Any:
    """atan(x) — 결과를 degree로 반환한다."""
    return sympy.deg(sympy.atan(x))


def _atan2_deg(y: Any, x: Any) -> Any:
    """atan2(y, x) — 결과를 degree로 반환한다."""
    return sympy.deg(sympy.atan2(y, x))


def _round(x: Any, ndigits: Any = 0) -> Any:
    """반올림한다. ndigits를 생략하면 정수로 반올림한다."""
    return sympy.Float(round(float(x), int(ndigits)))


def _cbrt(x: Any) -> Any:
    """세제곱근."""
    return sympy.root(x, 3)


def _nth_root(x: Any, n: Any) -> Any:
    """n제곱근. 예: root(8, 3) = 2"""
    return sympy.root(x, n)


# --- 목록(리스트) 집계 함수 ---
# "loads = [10 kN, 20 kN, 30 kN]" 처럼 [ ]로 감싼 목록 리터럴은 SymPy 파서가
# 별도 처리 없이도 그냥 파이썬 list로 계산해준다(대괄호는 파이썬 문법이라
# 파서가 원래 알고 있음). 여기 함수들은 그 목록을 받아 하나의 값으로 요약한다.
# 항목이 단위 있는 값(Pint Quantity)이어도 그대로 동작한다 — Quantity가
# +, <, > 연산자를 직접 구현하고 있어서(단, 차원이 다르면 에러) 파이썬
# 내장 sum()/max()/min()과 똑같이 쓸 수 있다.


def _agg_sum(items: Any) -> Any:
    """목록의 합. 빈 목록이면 0."""
    items = list(items)
    if not items:
        return sympy.Integer(0)
    total = items[0]
    for item in items[1:]:
        total = total + item
    return total


def _agg_max(items: Any) -> Any:
    """목록의 최댓값."""
    items = list(items)
    if not items:
        raise ValueError("빈 목록의 최댓값은 구할 수 없습니다")
    return max(items)


def _agg_min(items: Any) -> Any:
    """목록의 최솟값."""
    items = list(items)
    if not items:
        raise ValueError("빈 목록의 최솟값은 구할 수 없습니다")
    return min(items)


def _agg_avg(items: Any) -> Any:
    """목록의 평균."""
    items = list(items)
    if not items:
        raise ValueError("빈 목록의 평균은 구할 수 없습니다")
    return _agg_sum(items) / len(items)


def _agg_count(items: Any) -> Any:
    """목록의 항목 개수."""
    return sympy.Integer(len(list(items)))


#: 수식 안에서 함수처럼 쓸 수 있는 이름들 (SymPy 파서의 local_dict로 전달됨).
FUNCTIONS: dict[str, Callable[..., Any]] = {
    # 삼각함수 (degree 기준)
    "sin": _sin_deg,
    "cos": _cos_deg,
    "tan": _tan_deg,
    "asin": _asin_deg,
    "acos": _acos_deg,
    "atan": _atan_deg,
    "atan2": _atan2_deg,
    # 쌍곡선함수
    "sinh": sympy.sinh,
    "cosh": sympy.cosh,
    "tanh": sympy.tanh,
    # 지수/로그
    "exp": sympy.exp,
    "log": sympy.log,  # 자연로그
    "ln": sympy.log,  # 자연로그 별칭
    "log10": lambda x: sympy.log(x, 10),
    "log2": lambda x: sympy.log(x, 2),
    # 거듭제곱/근
    "sqrt": sympy.sqrt,
    "cbrt": _cbrt,
    "root": _nth_root,
    # 기타
    "abs": sympy.Abs,
    "round": _round,
    "ceil": sympy.ceiling,
    "floor": sympy.floor,
    # 목록 집계: sum([...]), max([...]), min([...]), avg/mean([...]), count([...])
    "sum": _agg_sum,
    "max": _agg_max,
    "min": _agg_min,
    "avg": _agg_avg,
    "mean": _agg_avg,
    "count": _agg_count,
}

#: 수식 안에서 변수처럼 쓸 수 있는 상수들.
CONSTANTS: dict[str, Any] = {
    "pi": sympy.pi,
    "e": sympy.E,
}
