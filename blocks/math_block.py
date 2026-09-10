"""
수식 블록 — 사용자가 수식을 입력하면 실시간으로 계산 결과를 표시한다.

구조:
    [입력 영역]  -> engine.evaluator.evaluate()  -> [결과 표시 영역]

기본적으로는 "입력 = 결과"를 파워포인트 글상자처럼 한 줄에 표시한다. 블록을
선택한 뒤 우측 가장자리 손잡이를 드래그해서 폭을 좁히면, 그 폭에 다 안 들어갈
때만 입력 줄과 "= 결과" 줄로 나뉜다(줄바꿈). 폭을 직접 지정한 적이 없으면
항상 내용에 맞춰 한 줄로 넓어진다.

평소에는 입력/결과를 rendering/math_renderer.py로 미리 렌더링해둔 이미지를
그대로 그리다가(paint), 더블클릭하면 TextBlock과 같은 방식으로 인라인
QGraphicsTextItem을 띄워 원문을 편집시킨다.

한글이 섞인 입력(예: "sigma_허용")은 mathtext 폰트가 한글 글리프를 지원하지
않아 math_renderer가 렌더링을 포기하고 빈 이미지를 돌려준다. 이 블록은 그런
경우 일반 텍스트로 대신 그려서, 한글 변수명도 깨지지 않고 보이게 한다.
"""

import re

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap
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
from engine.unit_manager import Quantity, format_unit_expression
from rendering.math_renderer import render_to_pixmap

# --- 서식 상수 ---
INPUT_FONT_SIZE = 14
TEXT_PADDING = 6
LINE_SPACING = 4
PLACEHOLDER_TEXT = "수식을 입력하세요"

TEXT_COLOR = QColor(0, 0, 0)
ERROR_COLOR = QColor(190, 30, 30)
PLACEHOLDER_COLOR = QColor(160, 160, 160)

#: 우측 폭 조절 손잡이 크기(px)와, 블록이 아무리 좁아져도 유지할 최소 폭.
_HANDLE_SIZE = 10.0
_MIN_WIDTH = 80.0


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


def _line_size(metrics: QFontMetrics, pixmap: QPixmap | None, fallback: str | None) -> tuple[float, float]:
    """(pixmap, 대체 텍스트) 한 줄이 차지할 (너비, 높이). 둘 다 없으면 (0, 0)."""
    if pixmap is not None:
        return float(pixmap.width()), float(pixmap.height())
    if fallback is not None:
        rect = metrics.boundingRect(fallback)
        return float(rect.width()), float(rect.height())
    return 0.0, 0.0


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


class _UnitEditor(QGraphicsTextItem):
    """
    결과의 표시 단위만 편집하는 작은 인라인 에디터.

    Ctrl+더블클릭으로 들어가며, 전체 수식이 아니라 단위 문자열 하나만
    입력받는다는 점만 빼면 _InlineTextEditor와 동일한 패턴이다.
    """

    def __init__(self, parent_block: "MathBlock") -> None:
        super().__init__(parent_block)
        self._parent_block = parent_block

    def focusOutEvent(self, event) -> None:  # noqa: N802
        """편집창 밖을 클릭하면 편집을 마무리한다."""
        super().focusOutEvent(event)
        self._parent_block.finish_unit_editing()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Enter로도 편집을 끝낼 수 있게 한다."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._parent_block.finish_unit_editing()
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
        # -> "F = 200 kN" 처럼 입력 자체가 이미 값이면 한 줄로만 표시됨
        # -> "A + B" 처럼 결과가 따로 필요하면 "A + B = 15 m" 한 줄로 합쳐서 표시
        # -> 선택 후 우측 손잡이로 폭을 좁히면 입력/결과 두 줄로 접힘(PPT 글상자처럼)
        # -> Ctrl+더블클릭하면 단위만 바로 바꿀 수 있음(예: "m" -> "mm", 값도 자동 환산)
    """

    BLOCK_TYPE = "math"

    def __init__(self, position: tuple[float, float] = (0.0, 0.0), block_id: str | None = None) -> None:
        super().__init__(position=position, block_id=block_id)

        self._input_text: str = ""
        self._result: EvalResult | None = None
        self._preferred_unit: str | None = None  # 속성 패널에서 지정한 결과 표시 단위
        self._manual_width: float | None = None  # 손잡이로 직접 지정한 폭. None이면 자동(항상 한 줄)

        # 각 줄은 (렌더링된 pixmap) 또는 (일반 텍스트로 그릴 문자열) 중 하나만 채워진다.
        self._input_pixmap: QPixmap | None = None
        self._input_fallback: str | None = None
        self._result_pixmap: QPixmap | None = None
        self._result_fallback: str | None = None
        # "입력 = 결과"를 한 줄로 합친 버전 (폭이 충분할 때 이걸 그린다).
        self._combined_pixmap: QPixmap | None = None
        self._combined_fallback: str | None = None
        self._one_line_mode: bool = True

        self._resizing = False
        self._resize_start_mouse = None
        self._resize_start_width = 0.0

        self._editor: _InlineTextEditor | None = None
        self._unit_editor: _UnitEditor | None = None

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)

    # --- 공개 API ---

    def set_input_text(self, text: str) -> None:
        """
        입력 수식 원문을 바꾸고 미리보기용 이미지(또는 대체 텍스트)를 다시 만든다.

        Note:
            계산기 습관대로 끝에 붙인 "="(예: "A + B =")는 여기서 미리 지운다.
            (자세한 이유는 engine.parser.strip_trailing_calculator_equals 참고.)

            여기서는 텍스트만 바꿀 뿐 재계산은 하지 않는다. 재계산은 이 블록만이
            아니라 전체 문서 순서에 영향을 주므로, DocumentScene.recalculate_all()이
            모든 MathBlock을 순서대로 evaluate()해야 한다 (계획서 5.1 계산 순서 규칙).
        """
        self._input_text = strip_trailing_calculator_equals(text)
        self._input_pixmap, self._input_fallback = _render_line(self._input_text)
        self._recompute_layout()

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
        self._recompute_layout()

    def preferred_unit(self) -> str:
        """현재 지정된 표시 단위. 지정 안 했으면 빈 문자열."""
        return self._preferred_unit or ""

    def set_manual_width(self, width: float | None) -> None:
        """
        폭을 직접 지정한다 (우측 손잡이 드래그로 호출됨).

        Args:
            width: 새 폭(px). None이면 "자동 크기"로 되돌아가 항상 한 줄로 넓어진다.
        """
        self.prepareGeometryChange()
        self._manual_width = max(_MIN_WIDTH, width) if width is not None else None
        self._one_line_mode = self._fits_in_one_line()
        self.update()

    def manual_width(self) -> float | None:
        """손잡이로 지정한 폭. 자동 크기 상태면 None."""
        return self._manual_width

    def evaluate(self, scope: Scope) -> None:
        """
        engine.evaluator.evaluate()로 이 블록의 수식을 계산하고 결과 표시를 갱신한다.

        Args:
            scope: 이 블록 "이전"(위쪽) 블록들이 채워둔 변수를 담은 Scope.
                   이 블록이 변수를 정의하면(예: "a = 100") scope에 등록되어,
                   같은 재계산 루프의 다음 블록들이 이어서 참조할 수 있다.
        """
        self._result = evaluate(self._input_text, scope)
        self._recompute_layout()

    def _recompute_layout(self) -> None:
        """
        입력/결과/표시단위 중 하나라도 바뀔 때마다 호출한다.

        결과 줄(분리 버전)과 "입력 = 결과"(한 줄로 합친 버전) 이미지를 다시 만들고,
        지금 폭(자동 또는 손잡이로 지정한 값)에 맞춰 한 줄/두 줄 중 무엇을
        보여줄지 정한다.
        """
        if self._result is None or self._result.is_error:
            self._result_pixmap, self._result_fallback = None, None
        else:
            line = self._result_line_text()
            self._result_pixmap, self._result_fallback = _render_line(line) if line else (None, None)

        combined = self._combined_line_text()
        self._combined_pixmap, self._combined_fallback = _render_line(combined) if combined else (None, None)

        self.prepareGeometryChange()
        self._one_line_mode = self._fits_in_one_line()
        self.update()

    def _combined_line_text(self) -> str | None:
        """"입력 = 결과"를 한 줄로 합친 문자열. 따로 합칠 결과가 없으면 입력 그대로."""
        if not self._input_text.strip():
            return None
        result_part = self._result_line_text()
        if result_part is None:
            return self._input_text
        return f"{self._input_text} {result_part}"

    def _fits_in_one_line(self) -> bool:
        """지금 폭에 "입력 = 결과"가 한 줄로 들어가는지 확인한다."""
        if self._manual_width is None:
            return True  # 손잡이로 줄인 적 없으면 항상 내용에 맞춰 한 줄로 넓어진다.
        metrics = QFontMetrics(self._plain_font())
        natural_width, _ = _line_size(metrics, self._combined_pixmap, self._combined_fallback)
        available = self._manual_width - TEXT_PADDING * 2 - _HANDLE_SIZE
        return natural_width <= available

    # --- QGraphicsItem 필수 구현 ---

    def boundingRect(self) -> QRectF:  # noqa: N802
        if self._editor is not None:
            width = self._manual_width if self._manual_width is not None else 220.0
            return QRectF(0, 0, max(width, 100.0), 24)
        if self._unit_editor is not None:
            return QRectF(0, 0, 100.0, 24)

        metrics = QFontMetrics(self._plain_font())

        if not self._input_text.strip():
            content_w, content_h = _line_size(metrics, None, PLACEHOLDER_TEXT)  # 안내 문구는 항상 한 줄
        elif self._one_line_mode:
            content_w, content_h = _line_size(metrics, self._combined_pixmap, self._combined_fallback)
        else:
            top_w, top_h = _line_size(metrics, self._input_pixmap, self._input_fallback)
            bottom_pixmap, bottom_text = self._bottom_line()
            bottom_w, bottom_h = _line_size(metrics, bottom_pixmap, bottom_text)
            content_w = max(top_w, bottom_w)
            content_h = top_h + (LINE_SPACING + bottom_h if bottom_h > 0 else 0.0)

        width = self._manual_width if self._manual_width is not None else content_w + TEXT_PADDING * 2
        height = content_h + TEXT_PADDING * 2

        width = max(width, 80.0)
        height = max(height, 28.0)
        return QRectF(0, 0, width, height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if self._editor is not None or self._unit_editor is not None:
            return

        metrics = QFontMetrics(self._plain_font())
        y = float(TEXT_PADDING)

        if not self._input_text.strip():
            self._draw_plain_line(painter, metrics, y, PLACEHOLDER_TEXT, PLACEHOLDER_COLOR)
        elif self._one_line_mode:
            self._draw_one_line(painter, y)
        else:
            y += self._draw_input_line(painter, metrics, y)
            self._draw_bottom_line(painter, metrics, y)

        if self.isSelected():
            rect = self.boundingRect()
            pen = QPen(QColor(0, 0, 0))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setBrush(QColor(255, 255, 255))
            painter.drawRect(self._handle_rect())

    def _draw_one_line(self, painter: QPainter, y: float) -> None:
        """"입력 = 결과"를 한 줄로 그린다."""
        if self._combined_pixmap is not None:
            painter.drawPixmap(TEXT_PADDING, int(y), self._combined_pixmap)
        elif self._combined_fallback is not None:
            metrics = QFontMetrics(self._plain_font())
            self._draw_plain_line(painter, metrics, y, self._combined_fallback, TEXT_COLOR)

    def _draw_input_line(self, painter: QPainter, metrics: QFontMetrics, y: float) -> float:
        """(두 줄 모드) 입력 줄을 그리고, 다음 줄이 시작할 y 증가분을 돌려준다."""
        if self._input_pixmap is not None:
            painter.drawPixmap(TEXT_PADDING, int(y), self._input_pixmap)
            return self._input_pixmap.height() + LINE_SPACING
        if self._input_fallback is not None:
            return self._draw_plain_line(painter, metrics, y, self._input_fallback, TEXT_COLOR)
        return 0.0

    def _draw_bottom_line(self, painter: QPainter, metrics: QFontMetrics, y: float) -> None:
        """(두 줄 모드) 결과/에러 줄을 그린다."""
        if self._result_pixmap is not None:
            painter.drawPixmap(TEXT_PADDING, int(y), self._result_pixmap)
        elif self._result_fallback is not None:
            self._draw_plain_line(painter, metrics, y, self._result_fallback, TEXT_COLOR)
        elif self._result is not None and self._result.is_error:
            self._draw_plain_line(painter, metrics, y, self._result.error, ERROR_COLOR)

    def _draw_plain_line(
        self, painter: QPainter, metrics: QFontMetrics, y: float, text: str, color: QColor
    ) -> float:
        """일반 폰트(한글 지원)로 한 줄을 그리고, 다음 줄이 시작할 y 오프셋 증가분을 돌려준다."""
        painter.setFont(self._plain_font())
        painter.setPen(color)
        painter.drawText(TEXT_PADDING, int(y) + metrics.ascent(), text)
        return metrics.height() + LINE_SPACING

    def _bottom_line(self) -> tuple[QPixmap | None, str | None]:
        """(두 줄 모드) 결과/에러 줄로 그릴 (pixmap, 텍스트) — 보여줄 게 없으면 (None, None)."""
        if self._result_pixmap is not None:
            return self._result_pixmap, None
        if self._result_fallback is not None:
            return None, self._result_fallback
        if self._result is not None and self._result.is_error:
            return None, self._result.error
        return None, None

    def _handle_rect(self) -> QRectF:
        """우측 가장자리 폭 조절 손잡이 (이 블록의 로컬 좌표계 기준)."""
        rect = self.boundingRect()
        return QRectF(rect.width() - _HANDLE_SIZE, rect.height() / 2 - _HANDLE_SIZE / 2, _HANDLE_SIZE, _HANDLE_SIZE)

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
        unit_text_override = None
        if self._preferred_unit and isinstance(value, Quantity):
            try:
                value = value.to(self._preferred_unit)
                # Pint의 기본 포맷터는 복합 단위를 항상 정해진 순서로 재배열해서
                # 보여준다("tonf*m"이라고 입력해도 "m*tf"로 앞뒤가 바뀌는 버그가
                # 있었다) — 사용자가 입력한 순서를 그대로 지키려면 직접 포맷해야 한다.
                unit_text_override = format_unit_expression(self._preferred_unit)
            except (pint.errors.DimensionalityError, pint.errors.UndefinedUnitError):
                pass  # 호환되지 않거나 알 수 없는 단위면 조용히 무시하고 원래 값을 보여준다

        formatted = format_value(value, unit_text_override=unit_text_override)
        if _strip_spaces(self._input_text).endswith(_strip_spaces(formatted)):
            # "a = 100" 처럼 입력 자체가 이미 값이면 중복 표시하지 않는다.
            # 공백은 무시하고 비교한다 — format_value()는 숫자와 단위 사이에 항상
            # 공백을 넣어 "5 M"로 만드는데, 사용자가 "5M"처럼 붙여 쓰면 문자열이
            # 정확히 일치하지 않아서 중복 표시가 새는 버그가 있었다.
            return None
        return f"= {formatted}"

    # --- 폭 조절 (드래그) ---

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """
        선택된 상태에서 우측 손잡이를 누르면 폭 조절 모드로 들어간다.

        Note:
            손잡이가 아닌 곳을 누르면 그냥 super()에 맡긴다 — BaseBlock이 설정한
            ItemIsMovable 플래그 덕분에 Qt가 알아서 드래그 이동을 처리해준다.
        """
        if self.isSelected() and self._handle_rect().contains(event.pos()):
            self._resizing = True
            self._resize_start_mouse = event.scenePos()
            self._resize_start_width = self.boundingRect().width()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._resizing and self._resize_start_mouse is not None:
            delta_x = event.scenePos().x() - self._resize_start_mouse.x()
            self.set_manual_width(self._resize_start_width + delta_x)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._resizing:
            self._resizing = False
            self._resize_start_mouse = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # --- 편집 모드 ---

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """
        더블클릭하면 편집 모드로 들어간다.

        Ctrl을 누른 채 더블클릭하면 전체 수식이 아니라 결과의 "표시 단위"만
        고칠 수 있다 (예: "m" -> "mm"이라고 치면 값도 자동으로 환산되어 보임).
        손잡이를 (Ctrl 여부와 무관하게) 더블클릭한 경우는 무시한다.
        """
        if self._handle_rect().contains(event.pos()):
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.start_unit_editing()
        else:
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

    # --- 단위만 편집하는 모드 (Ctrl+더블클릭) ---

    def _has_convertible_result(self) -> bool:
        """지금 결과가 단위 있는 값(Quantity)이라 단위를 바꿔볼 수 있는 상태인지."""
        return self._result is not None and not self._result.is_error and isinstance(self._result.value, Quantity)

    def _current_unit_text(self) -> str:
        """지금 화면에 표시 중인 단위 문자열 (표시 단위를 따로 지정했으면 그걸, 아니면 자동 정리된 단위)."""
        if self._preferred_unit:
            return self._preferred_unit
        if self._has_convertible_result():
            return f"{self._result.value.units:~P}"
        return ""

    def start_unit_editing(self) -> None:
        """
        단위만 편집하는 인라인 에디터를 띄운다.

        Note:
            결과가 단위 있는 값(Quantity)일 때만 의미가 있다 — 에러 상태이거나
            단위 없는 순수 숫자·불리언 결과면 바꿀 단위 자체가 없으므로 무시한다.
        """
        if self._editor is not None or self._unit_editor is not None:
            return
        if not self._has_convertible_result():
            return

        self.prepareGeometryChange()
        self._unit_editor = _UnitEditor(self)
        self._unit_editor.setFont(self._plain_font())
        self._unit_editor.setDefaultTextColor(Qt.GlobalColor.black)
        self._unit_editor.setPlainText(self._current_unit_text())
        self._unit_editor.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self._unit_editor.setPos(0, 0)

        self._unit_editor.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self._unit_editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self._unit_editor.setTextCursor(cursor)

    def finish_unit_editing(self) -> None:
        """
        입력한 단위를 표시 단위로 확정한다.

        Note:
            set_preferred_unit()이 이미 "호환 안 되거나 알 수 없는 단위면 조용히
            무시하고 원래 값을 보여준다"를 처리하므로, 여기서는 값을 그대로
            넘기기만 하면 된다 — 재계산이 아니라 표시 방식만 바뀌는 것이므로
            scene.recalculate_all()을 부를 필요는 없다.
        """
        if self._unit_editor is None:
            return

        new_unit = self._unit_editor.toPlainText()

        editor = self._unit_editor
        self._unit_editor = None
        editor.setParentItem(None)
        if editor.scene() is not None:
            editor.scene().removeItem(editor)

        self.set_preferred_unit(new_unit)

    # --- 직렬화 ---

    def serialize(self) -> dict:
        """공통 필드(BaseBlock) + 수식 원문 + 표시 단위 + (지정했다면) 폭을 담는다."""
        data = super().serialize()
        data["expression"] = self._input_text
        data["display_unit"] = self._preferred_unit or ""
        if self._manual_width is not None:
            data["width"] = self._manual_width
        return data

    def deserialize(self, data: dict) -> None:
        """저장된 dict로부터 위치 + 수식 원문 + 표시 단위 + 폭을 복원한다 (계산은 별도 recalculate_all()이 담당)."""
        super().deserialize(data)
        self._preferred_unit = data.get("display_unit") or None
        self._manual_width = data.get("width")
        self.set_input_text(data.get("expression", ""))


def format_value(value, unit_text_override: str | None = None) -> str:
    """
    계산 결과를 사람이 읽기 좋은 문자열로 바꾼다.

    Args:
        value: 계산 결과 (숫자, bool, 또는 Quantity)
        unit_text_override: 단위 부분에 이 문자열을 그대로 쓴다. 지정 안 하면
            Pint의 기본 포맷터(~P)로 단위를 만든다 — 단, 이 기본 포맷터는
            복합 단위의 순서를 사용자가 입력한 대로 지켜주지 않으므로(예:
            "tonf*m"을 넣어도 "m·tf"로 뒤바뀜), 순서를 지켜야 할 때는
            engine.unit_manager.format_unit_expression()으로 만든 문자열을
            여기 넘긴다 (blocks/math_block.py의 _result_line_text 참고).
    """
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, Quantity):
        # 단위가 붙은 값은 float()으로 바로 못 바꾼다(Pint가 일부러 막아둠 —
        # "몇 mm인지" 같은 단위 없는 숫자로의 변환은 의미가 불분명하기 때문).
        # magnitude(숫자)와 units(단위)를 따로 포맷해서 합친다.
        magnitude_text = _format_number(value.magnitude)
        unit_text = unit_text_override if unit_text_override is not None else f"{value.units:~P}"
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
