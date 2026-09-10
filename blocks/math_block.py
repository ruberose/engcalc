"""
수식 블록 — 사용자가 수식을 입력하면 실시간으로 계산 결과를 표시한다.

구조:
    [입력 영역]  -> engine.evaluator.evaluate()  -> [결과 표시 영역]

평소에는 입력/결과를 rendering/math_renderer.py로 미리 렌더링해둔 이미지를
그대로 그리다가(paint), 더블클릭하면 TextBlock과 같은 방식으로 인라인
QGraphicsTextItem을 띄워 원문을 편집시킨다.

한글이 섞인 입력(예: "sigma_허용")은 mathtext 폰트가 한글 글리프를 지원하지
않아 math_renderer가 렌더링을 포기하고 빈 이미지를 돌려준다. 이 블록은 그런
경우 일반 텍스트로 대신 그려서, 한글 변수명도 깨지지 않고 보이게 한다.
"""

import re

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

import pint

from blocks.base_block import BaseBlock
from engine.evaluator import EvalResult, evaluate
from engine.parser import strip_trailing_calculator_equals
from engine.scope import Scope
from engine.unit_manager import Quantity
from rendering.math_renderer import render_to_pixmap

# --- 서식 상수 ---
INPUT_FONT_SIZE = 14
TEXT_PADDING = 6
LINE_SPACING = 4
PLACEHOLDER_TEXT = "수식을 입력하세요"

TEXT_COLOR = QColor(0, 0, 0)
ERROR_COLOR = QColor(190, 30, 30)
PLACEHOLDER_COLOR = QColor(160, 160, 160)


def _strip_spaces(text: str) -> str:
    """공백을 전부 지운다 ("5M"과 "5 M"을 같은 것으로 비교하기 위한 용도)."""
    return re.sub(r"\s+", "", text)


def _render_line(text: str, font_size: int = INPUT_FONT_SIZE) -> tuple[QPixmap | None, str | None]:
    """
    한 줄을 mathtext로 렌더링해본다.

    Returns:
        (pixmap, None): mathtext 렌더링 성공 — pixmap을 그대로 그리면 됨
        (None, text): 렌더링 불가(빈 문자열이거나 한글 등 비ASCII 포함) — 일반 텍스트로 그려야 함
        (None, None): 표시할 내용 자체가 없음
    """
    if not text.strip():
        return None, None
    pixmap = render_to_pixmap(text, font_size)
    if pixmap.isNull():
        return None, text
    return pixmap, None


class _InlineTextEditor(QGraphicsTextItem):
    """MathBlock이 편집 모드일 때만 잠깐 만들어지는 실제 입력창 (TextBlock과 동일한 패턴)."""

    def __init__(self, parent_block: "MathBlock") -> None:
        super().__init__(parent_block)
        self._parent_block = parent_block

    def focusOutEvent(self, event) -> None:  # noqa: N802
        """편집창 밖을 클릭하면 편집을 마무리한다."""
        super().focusOutEvent(event)
        self._parent_block.finish_editing()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Enter로도 편집을 끝낼 수 있게 한다 (수식 한 줄은 여러 줄이 필요 없으므로)."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._parent_block.finish_editing()
            event.accept()
            return
        super().keyPressEvent(event)


class MathBlock(BaseBlock):
    """
    수식 블록.

    사용 예:
        block = MathBlock(position=(100, 200))
        block.set_input_text("F = 200 kN")
        block.evaluate(scope)
        # -> 결과 영역에 값이 표시되고, 대입문이면 scope에 등록됨
    """

    BLOCK_TYPE = "math"

    def __init__(self, position: tuple[float, float] = (0.0, 0.0), block_id: str | None = None) -> None:
        super().__init__(position=position, block_id=block_id)

        self._input_text: str = ""
        self._result: EvalResult | None = None
        self._preferred_unit: str | None = None  # 속성 패널에서 지정한 결과 표시 단위

        # 각 줄은 (렌더링된 pixmap) 또는 (일반 텍스트로 그릴 문자열) 중 하나만 채워진다.
        self._input_pixmap: QPixmap | None = None
        self._input_fallback: str | None = None
        self._result_pixmap: QPixmap | None = None
        self._result_fallback: str | None = None

        self._editor: _InlineTextEditor | None = None

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)

    # --- 공개 API ---

    def set_input_text(self, text: str) -> None:
        """
        입력 수식 원문을 바꾸고 미리보기용 이미지(또는 대체 텍스트)를 다시 만든다.

        Note:
            계산기 습관대로 끝에 붙인 "="(예: "A + B =")는 여기서 미리 지운다.
            engine.evaluator도 계산할 때 그 "="를 무시하긴 하지만, 화면에 보여줄
            self._input_text 자체에서 안 지우면 "A + B ="라는 입력 줄 끝의 "="와
            그 아래 "= 10m" 결과 줄의 "="가 나란히 보여서 등호가 두 번 있는
            것처럼 보였다(버그체크 중 발견).

            여기서는 텍스트만 바꿀 뿐 재계산은 하지 않는다. 재계산은 이 블록만이
            아니라 전체 문서 순서에 영향을 주므로, DocumentScene.recalculate_all()이
            모든 MathBlock을 순서대로 evaluate()해야 한다 (계획서 5.1 계산 순서 규칙).
        """
        self._input_text = strip_trailing_calculator_equals(text)
        self._input_pixmap, self._input_fallback = _render_line(self._input_text)
        self.prepareGeometryChange()
        self.update()

    def input_text(self) -> str:
        """현재 입력된 수식 원문을 반환한다."""
        return self._input_text

    def result(self) -> EvalResult | None:
        """가장 최근 계산 결과를 반환한다 (아직 계산 전이면 None)."""
        return self._result

    def set_preferred_unit(self, unit_text: str) -> None:
        """
        결과를 표시할 때 쓸 단위를 지정한다 (속성 패널의 "표시 단위" 입력용).

        Args:
            unit_text: "kPa" 같은 단위 문자열. 빈 문자열이면 자동으로 정리된
                       단위(engine.unit_manager.simplify 결과)를 그대로 쓴다.

        Note:
            표시 방식만 바꿀 뿐 재계산은 하지 않는다 — scope에 저장된 실제 값은
            건드리지 않으므로, 이 블록을 참조하는 다른 블록의 계산에는 영향이 없다.
        """
        self._preferred_unit = unit_text.strip() or None
        self._refresh_result_display()

    def preferred_unit(self) -> str:
        """현재 지정된 표시 단위. 지정 안 했으면 빈 문자열."""
        return self._preferred_unit or ""

    def evaluate(self, scope: Scope) -> None:
        """
        engine.evaluator.evaluate()로 이 블록의 수식을 계산하고 결과 표시를 갱신한다.

        Args:
            scope: 이 블록 "이전"(위쪽) 블록들이 채워둔 변수를 담은 Scope.
                   이 블록이 변수를 정의하면(예: "a = 100") scope에 등록되어,
                   같은 재계산 루프의 다음 블록들이 이어서 참조할 수 있다.
        """
        self._result = evaluate(self._input_text, scope)
        self._refresh_result_display()

    def _refresh_result_display(self) -> None:
        """_result를 기준으로 결과 줄 이미지를 다시 만든다 (재계산은 하지 않음)."""
        if self._result is None or self._result.is_error:
            self._result_pixmap, self._result_fallback = None, None
        else:
            line = self._result_line_text()
            self._result_pixmap, self._result_fallback = _render_line(line) if line else (None, None)

        self.prepareGeometryChange()
        self.update()

    # --- QGraphicsItem 필수 구현 ---

    def boundingRect(self) -> QRectF:  # noqa: N802
        if self._editor is not None:
            return QRectF(0, 0, 220, 24)

        metrics = QFontMetrics(self._plain_font())
        width, height = self._top_line_size(metrics)

        bottom_pixmap, bottom_text = self._bottom_line()
        if bottom_pixmap is not None:
            width = max(width, bottom_pixmap.width())
            height += LINE_SPACING + bottom_pixmap.height()
        elif bottom_text is not None:
            rect = metrics.boundingRect(bottom_text)
            width = max(width, rect.width())
            height += LINE_SPACING + rect.height()

        width = max(width + TEXT_PADDING * 2, 80)
        height = max(height + TEXT_PADDING * 2, 28)
        return QRectF(0, 0, width, height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if self._editor is not None:
            return

        metrics = QFontMetrics(self._plain_font())
        y = TEXT_PADDING

        # --- 입력 줄 ---
        if self._input_pixmap is not None:
            painter.drawPixmap(TEXT_PADDING, y, self._input_pixmap)
            y += self._input_pixmap.height() + LINE_SPACING
        elif self._input_fallback is not None:
            y += self._draw_plain_line(painter, metrics, y, self._input_fallback, TEXT_COLOR)
        else:
            y += self._draw_plain_line(painter, metrics, y, PLACEHOLDER_TEXT, PLACEHOLDER_COLOR)

        # --- 결과/에러 줄 ---
        if self._result_pixmap is not None:
            painter.drawPixmap(TEXT_PADDING, y, self._result_pixmap)
        elif self._result_fallback is not None:
            self._draw_plain_line(painter, metrics, y, self._result_fallback, TEXT_COLOR)
        elif self._result is not None and self._result.is_error:
            self._draw_plain_line(painter, metrics, y, self._result.error, ERROR_COLOR)

        if self.isSelected():
            pen = painter.pen()
            pen.setColor(QColor(0, 0, 0))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.boundingRect())

    def _draw_plain_line(self, painter: QPainter, metrics: QFontMetrics, y: int, text: str, color: QColor) -> int:
        """일반 폰트(한글 지원)로 한 줄을 그리고, 다음 줄이 시작할 y 오프셋 증가분을 돌려준다."""
        painter.setFont(self._plain_font())
        painter.setPen(color)
        painter.drawText(TEXT_PADDING, y + metrics.ascent(), text)
        return metrics.height() + LINE_SPACING

    def _top_line_size(self, metrics: QFontMetrics) -> tuple[int, int]:
        """입력 줄(또는 안내 문구)이 차지할 (너비, 높이)."""
        if self._input_pixmap is not None:
            return self._input_pixmap.width(), self._input_pixmap.height()
        text = self._input_fallback if self._input_fallback is not None else PLACEHOLDER_TEXT
        rect = metrics.boundingRect(text)
        return rect.width(), rect.height()

    def _bottom_line(self) -> tuple[QPixmap | None, str | None]:
        """결과/에러 줄로 그릴 (pixmap, 텍스트) — 보여줄 게 없으면 (None, None)."""
        if self._result_pixmap is not None:
            return self._result_pixmap, None
        if self._result_fallback is not None:
            return None, self._result_fallback
        if self._result is not None and self._result.is_error:
            return None, self._result.error
        return None, None

    def _plain_font(self) -> QFont:
        """시스템 기본 UI 폰트 — 한글도 깨지지 않고 표시된다."""
        font = QFont()
        font.setPointSize(INPUT_FONT_SIZE)
        return font

    def _result_line_text(self) -> str | None:
        """결과 줄에 표시할 문자열. 보여줄 게 없으면 None."""
        if self._result is None or self._result.value is None:
            return None

        value = self._result.value
        if self._preferred_unit and isinstance(value, Quantity):
            try:
                value = value.to(self._preferred_unit)
            except (pint.errors.DimensionalityError, pint.errors.UndefinedUnitError):
                pass  # 호환되지 않거나 알 수 없는 단위면 조용히 무시하고 원래 값을 보여준다

        formatted = format_value(value)
        if _strip_spaces(self._input_text).endswith(_strip_spaces(formatted)):
            # "a = 100" 처럼 입력 자체가 이미 값이면 중복 표시하지 않는다.
            # 공백은 무시하고 비교한다 — format_value()는 숫자와 단위 사이에 항상
            # 공백을 넣어 "5 M"로 만드는데, 사용자가 "5M"처럼 붙여 쓰면 문자열이
            # 정확히 일치하지 않아서 중복 표시가 새는 버그가 있었다.
            return None
        return f"= {formatted}"

    # --- 편집 모드 ---

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """더블클릭하면 편집 모드로 들어간다."""
        self.start_editing()
        event.accept()

    def start_editing(self) -> None:
        """인라인 편집기를 만들어 현재 입력 원문을 채워 넣고 포커스를 준다."""
        if self._editor is not None:
            return

        self.prepareGeometryChange()
        self._editor = _InlineTextEditor(self)
        self._editor.setFont(self._plain_font())
        self._editor.setDefaultTextColor(Qt.GlobalColor.black)
        self._editor.setPlainText(self._input_text)
        self._editor.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self._editor.setPos(0, 0)

        self._editor.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self._editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self._editor.setTextCursor(cursor)

    def finish_editing(self) -> None:
        """
        편집기 내용을 확정하고, 캔버스(DocumentScene)에 전체 재계산을 요청한다.

        Note:
            블록은 다른 블록을 직접 알지 못한다("모듈 분리 원칙" — 블록끼리 직접 참조 금지).
            그래서 재계산은 항상 자신이 속한 씬에게 위임한다.
        """
        if self._editor is None:
            return

        self.set_input_text(self._editor.toPlainText())

        editor = self._editor
        self._editor = None
        editor.setParentItem(None)
        if editor.scene() is not None:
            editor.scene().removeItem(editor)

        self.update()

        scene = self.scene()
        if scene is not None and hasattr(scene, "recalculate_all"):
            scene.recalculate_all()

    # --- 직렬화 ---

    def serialize(self) -> dict:
        """공통 필드(BaseBlock) + 수식 원문 + 표시 단위를 함께 담는다."""
        data = super().serialize()
        data["expression"] = self._input_text
        data["display_unit"] = self._preferred_unit or ""
        return data

    def deserialize(self, data: dict) -> None:
        """저장된 dict로부터 위치 + 수식 원문 + 표시 단위를 복원한다 (계산은 별도 recalculate_all()이 담당)."""
        super().deserialize(data)
        self._preferred_unit = data.get("display_unit") or None
        self.set_input_text(data.get("expression", ""))


def format_value(value) -> str:
    """계산 결과를 사람이 읽기 좋은 문자열로 바꾼다."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, Quantity):
        # 단위가 붙은 값은 float()으로 바로 못 바꾼다(Pint가 일부러 막아둠 —
        # "몇 mm인지" 같은 단위 없는 숫자로의 변환은 의미가 불분명하기 때문).
        # magnitude(숫자)와 units(단위)를 따로 포맷해서 합친다.
        magnitude_text = _format_number(value.magnitude)
        unit_text = f"{value.units:~P}"
        return f"{magnitude_text} {unit_text}".strip()
    return _format_number(value)


def _format_number(value) -> str:
    """단위 없는 순수 숫자를 사람이 읽기 좋은 문자열로 바꾼다."""
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return str(value)
    if as_float == int(as_float):
        return str(int(as_float))
    return f"{as_float:.6g}"
