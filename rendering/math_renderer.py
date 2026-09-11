"""
수식/결과 문자열을 matplotlib mathtext로 렌더링해 QPixmap으로 만든다.

mathtext는 '^'를 위첨자로, '_'를 아래첨자로 이미 해석해주기 때문에,
엔지니어링 계산식(x^2, F_y 등)을 별도 변환 없이도 자연스럽게 예쁜 수식처럼
보여줄 수 있다. KaTeX 웹뷰 같은 무거운 의존성 없이 requirements.txt에 이미
있는 matplotlib만으로 처리한다.

Note:
    matplotlib의 저수준 API인 MathTextParser.to_rgba()는 버전에 따라
    시그니처가 바뀌어왔다(예: 3.11에서 제거됨). 그래서 여기서는 항상 안정적으로
    쓸 수 있는 공개 API인 Figure.savefig(bbox_inches="tight")로 PNG를 만들고,
    그걸 Qt가 직접 디코딩하게 한다.
"""

import io

import matplotlib

matplotlib.use("Agg")  # GUI 백엔드 없이 이미지로만 렌더링
from matplotlib.figure import Figure  # noqa: E402 (matplotlib.use()보다 뒤에 와야 함)

from PySide6.QtGui import QPixmap  # noqa: E402

#: 이 글자가 하나라도 있으면 mathtext로 예쁘게 그리지 않는다. mathtext는 이
#: 문자들(LaTeX 문법: "\frac{}", "x^{10}" 등)을 알아서 그럴듯하게 그려주지만,
#: 정작 계산 엔진(engine/evaluator.py의 SymPy 파서)은 이 문법을 전혀 이해하지
#: 못해서 항상 에러가 난다. "화면엔 예쁘게 보이는데 계산은 안 되는" 혼란을
#: 막으려면, 계산이 안 될 걸 화면에서도 예쁘게 보여주면 안 된다 — 그래서
#: 이런 문자가 섞이면 아예 렌더링을 포기하고 원문 그대로(plain text)를
#: 보여주도록 한다(호출하는 쪽이 대체 표시를 맡음).
_LATEX_MARKUP_CHARS = ("\\", "{", "}")


def render_to_pixmap(text: str, font_size: int = 14, dpi: int = 150, color: str = "black") -> QPixmap:
    """
    문자열을 수식처럼 렌더링한다 (mathtext의 수식 모드로 감싸서 그림).

    Args:
        text: 렌더링할 문자열. 예: "a=100", "a*sin(30)=50"
        font_size: 폰트 크기(pt)
        dpi: 해상도
        color: 글자 색 (matplotlib이 이해하는 색 이름 또는 hex)

    Returns:
        렌더링된 이미지(배경 투명). mathtext 문법 오류나 LaTeX 문법(위
        _LATEX_MARKUP_CHARS 참고) 포함 등으로 실패하면 빈 QPixmap을 반환한다 —
        호출하는 쪽(MathBlock)이 이를 "렌더링할 것 없음"으로 취급하고 원본
        텍스트로 대체해서 그리면 되므로, 여기서 예외를 앱 밖으로 던지지 않는다.

    Note:
        mathtext 기본 폰트(dejavusans 등)에는 한글 글리프가 없어서,
        "sigma_허용" 같은 한글 섞인 변수명을 그대로 넣으면 깨진 기호로 보인다.
        그래서 텍스트에 ASCII가 아닌 문자가 섞여 있으면 아예 렌더링을 포기하고
        빈 QPixmap을 돌려준다 — 호출하는 쪽이 일반(한글 지원) 폰트로 대신 그린다.
    """
    if not text.isascii() or any(ch in text for ch in _LATEX_MARKUP_CHARS):
        return QPixmap()

    safe_text = text.replace("$", r"\$")

    try:
        fig = Figure(figsize=(0.1, 0.1))
        fig.patch.set_alpha(0)
        fig.text(0, 0, f"${safe_text}$", fontsize=font_size, color=color)

        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0.02)
    except Exception:  # noqa: BLE001 - 렌더링 실패는 치명적이지 않으므로 폭넓게 잡고 빈 픽스맵으로 대체
        return QPixmap()

    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap
