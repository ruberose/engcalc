"""
계산 문법(sqrt(), sigma, a/b 등)을 화면 표시용 mathtext 기호(√, σ, 분수)로 바꾼다.

blocks/math_block.py가 이 함수의 결과를 오직 렌더링(rendering/math_renderer.py)
에만 쓴다 — 계산(engine.evaluator.evaluate)에 넘어가는 원문은 절대 건드리지
않는다. 곱하기를 "·"로 보여주는 것과 완전히 같은 원칙("표시만 바꾸고 계산용
원문은 그대로 둔다")을 sqrt/그리스 문자/분수로 넓힌 것이다.

안전장치: 원본에 이미 백슬래시나 중괄호가 있으면(사용자가 실수로 LaTeX을
타이핑한 경우) 아무 것도 바꾸지 않고 그대로 돌려준다. 이런 텍스트는
engine/evaluator.py에서도 이미 "LaTeX 미지원" 에러로 처리되므로, 여기서
화면만 예뻐지면 "보기엔 되는데 계산은 안 된다"는 혼란이 다시 생긴다
(과거 커밋 6c334c0에서 정리했던 바로 그 문제).
"""

import re

#: 이 문자가 하나라도 있으면 변환을 포기하고 원문 그대로 돌려준다(위 안전장치 참고).
#: blocks/math_block.py도 "우리가 직접 만들어 넣은 문법인지" 판단할 때 이 목록을
#: 그대로 재사용한다(render_to_pixmap의 skip_markup_guard로 넘길지 결정).
MARKUP_CHARS = ("\\", "{", "}")

#: sqrt(X) -> \sqrt{X}, cbrt(X) -> \sqrt[3]{X}, root(X, N) -> \sqrt[N]{X}.
#: 함수 이름 바로 뒤에 "("가 붙어있을 때만 매치한다(공백 없이 — 보통 입력 습관과 일치).
#: 식별자 일부로 쓰인 경우("myroot(", "cbrtx(")는 앞/뒤 경계 검사로 걸러낸다.
_FUNC_CALL_PATTERN = re.compile(r"(?<![A-Za-z0-9_])(sqrt|cbrt|root)\(")

#: mathtext가 실제 그리스 문자 글리프로 그려주는 표준 이름들("\alpha" 등).
#: 대문자는 라틴 대문자와 모양이 다른 것들만 있다(Alpha/Beta 등은 라틴 대문자와
#: 똑같이 생겨서 LaTeX에도 별도 명령어가 없음).
_GREEK_NAMES = (
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma",
    "tau", "upsilon", "phi", "chi", "psi", "omega",
    "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon",
    "Phi", "Psi", "Omega",
)

# 식별자 경계 검사: 앞뒤가 영문자/숫자로 안 이어질 때만 매치한다. 밑줄은 경계로
# "치지 않는다"(제외 목록에 없음) — "sigma_allow"의 "sigma"도 잡아야 첨자와
# 조합해서 "\sigma_{allow}"를 만들 수 있기 때문이다.
_GREEK_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(sorted(_GREEK_NAMES, key=len, reverse=True)) + r")(?![A-Za-z0-9])"
)

#: 밑줄 뒤에 (영문/한글/숫자) 글자가 2개 이상 이어지면 mathtext가 한 글자만
#: 첨자로 인식하는 문제가 있어 중괄호로 묶는다("sigma_allow" -> "sigma_{allow}").
#: 한 글자짜리 첨자(F_y 등)는 이미 잘 그려지므로 건드리지 않는다.
_MULTICHAR_SUBSCRIPT_PATTERN = re.compile(r"_([A-Za-z0-9가-힣]{2,})(?![A-Za-z0-9가-힣])")


def to_symbolic_display(text: str) -> str:
    """
    계산 문법을 화면 표시용 기호(√, 그리스 문자, 분수)로 바꾼다.

    Args:
        text: 곱하기 "·" 치환 등 다른 표시용 처리가 이미 끝난 뒤의 문자열
              (blocks/math_block.py의 _display_text 참고).

    Returns:
        변환된 문자열. 원본에 백슬래시/중괄호가 있으면 건드리지 않고 그대로
        돌려준다. 변환 도중 예상 못한 문제(괄호가 안 맞는 등)가 생기면, 그
        부분만 원문 그대로 두거나(함수 호출 단위) 실패 시 전체를 원문으로
        되돌린다 — 표시 전용 기능이 실패해서 블록 렌더링 자체가 깨지면 안 된다.
    """
    if any(ch in text for ch in MARKUP_CHARS):
        return text
    try:
        return _transform(text)
    except Exception:  # noqa: BLE001 - 표시 전용 변환이므로 실패해도 원문으로 안전하게 대체
        return text


def _transform(text: str) -> str:
    """분수(최상위 "/"가 정확히 1개일 때) -> 루트 함수 호출 -> 그리스 문자/첨자 순으로 시도한다."""
    fraction = _wrap_fraction(text)
    if fraction is not None:
        return fraction
    return _wrap_roots_and_greek(text)


def _wrap_fraction(text: str) -> str | None:
    """
    최상위(괄호 밖) 깊이의 "/"가 정확히 1개일 때만 \\frac{}{}로 감싼다.

    Returns:
        분수로 바꿨으면 그 결과, 아니면 None(호출부가 다른 변환을 시도해야 함을
        알 수 있게). "/"가 0개면 분수가 아니고, 2개 이상("a/b/c")이면 어느
        쪽으로 묶어야 할지 모호하므로 — 잘못 묶어서 계산 순서가 달라 보이게
        만드느니 — 안전하게 건드리지 않는다.
    """
    parts = _split_top_level(text, "/")
    if parts is None or len(parts) != 2:
        return None
    left, right = parts
    if not left.strip() or not right.strip():
        return None  # "a/" 같은 비정상 입력은 건드리지 않는다
    return f"\\frac{{{_transform(left)}}}{{{_transform(right)}}}"


def _wrap_roots_and_greek(text: str) -> str:
    """sqrt/cbrt/root 함수 호출을 \\sqrt{}로 바꾸고, 나머지 구간엔 그리스 문자/첨자 표시를 적용한다."""
    pieces: list[str] = []
    pos = 0
    for match in _FUNC_CALL_PATTERN.finditer(text):
        if match.start() < pos:
            continue  # 이미 처리한 바깥쪽 함수 호출 안에 중첩된 매치 — 건너뜀

        pieces.append(_apply_greek_and_subscript(text[pos : match.start()]))

        func_name = match.group(1)
        open_paren = match.end() - 1
        close_paren = _find_matching_paren(text, open_paren)
        if close_paren is None:
            pieces.append(text[match.start() : match.end()])
            pos = match.end()
            continue

        inner = text[open_paren + 1 : close_paren]
        if func_name == "root":
            args = _split_top_level(inner, ",")
            if args is not None and len(args) == 2:
                radicand, degree = args
                pieces.append(f"\\sqrt[{_transform(degree.strip())}]{{{_transform(radicand.strip())}}}")
            else:
                pieces.append(text[match.start() : close_paren + 1])  # 인자가 2개가 아니면 그대로 둠
        elif func_name == "cbrt":
            pieces.append(f"\\sqrt[3]{{{_transform(inner)}}}")
        else:  # sqrt
            pieces.append(f"\\sqrt{{{_transform(inner)}}}")

        pos = close_paren + 1

    pieces.append(_apply_greek_and_subscript(text[pos:]))
    return "".join(pieces)


def _apply_greek_and_subscript(text: str) -> str:
    """그리스 문자 이름을 실제 기호로, 밑줄 뒤 여러 글자 첨자를 중괄호로 묶는다."""
    text = _GREEK_PATTERN.sub(lambda m: "\\" + m.group(1), text)
    text = _MULTICHAR_SUBSCRIPT_PATTERN.sub(lambda m: "_{" + m.group(1) + "}", text)
    return text


def _find_matching_paren(text: str, open_index: int) -> int | None:
    """text[open_index]가 "("일 때, 그와 짝지어지는 ")"의 인덱스. 못 찾으면 None."""
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def _split_top_level(text: str, separator: str) -> list[str] | None:
    """
    최상위(괄호 밖) 깊이에서만 separator로 text를 나눈다.

    Returns:
        나뉜 조각들의 리스트. separator가 최상위에 하나도 없으면 None
        (분수의 경우 "나눗셈 아님", 콤마의 경우 "인자 하나짜리"를 구분하기 위함).
    """
    depth = 0
    split_positions = []
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == separator and depth == 0:
            split_positions.append(i)
    if not split_positions:
        return None
    parts = []
    start = 0
    for pos in split_positions:
        parts.append(text[start:pos])
        start = pos + 1
    parts.append(text[start:])
    return parts
