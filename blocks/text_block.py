"""
텍스트 블록.

캔버스 위에서 제목·설명 등 자유 서식 텍스트를 표시하는 블록.
평소에는 자신이 직접 텍스트를 그리다가(paint), 더블클릭하면
편집용 QGraphicsTextItem을 잠깐 덧씌워서 편집시키고, 편집이 끝나면
그 내용을 다시 자기 것으로 흡수하는 방식으로 동작한다.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from blocks.base_block import BaseBlock

# --- 텍스트 블록 기본 서식 ---
DEFAULT_FONT_SIZE = 14
DEFAULT_TEXT = "텍스트를 입력하세요"
TEXT_PADDING = 4


class _InlineTextEditor(QGraphicsTextItem):
    """
    TextBlock이 편집 모드일 때만 잠깐 만들어지는 실제 편집 위젯.

    QGraphicsTextItem은 자체적으로 커서·선택·IME 입력을 다 처리해주므로,
    편집 UI를 직접 구현하는 대신 이 표준 위젯을 빌려 쓰고,
    포커스를 잃는 순간(focusOutEvent) 부모 TextBlock에게 "편집 끝났다"고 알려준다.
    """

    def __init__(self, parent_block: "TextBlock") -> None:
        super().__init__(parent_block)
        self._parent_block = parent_block

    def focusOutEvent(self, event) -> None:  # noqa: N802
        """편집창 밖을 클릭하는 등 포커스를 잃으면 편집을 마무리한다."""
        super().focusOutEvent(event)
        self._parent_block.finish_editing()


class TextBlock(BaseBlock):
    """
    자유 서식 텍스트 블록.

    구조:
        평상시: paint()가 self._text를 직접 그림 (가볍고 빠름)
        편집 중: _InlineTextEditor 자식 아이템이 화면을 덮고 실제 입력을 받음

    사용 예:
        block = TextBlock(position=(100, 50))
        block.set_text("1. 설계조건")
        scene.addItem(block)
        # 캔버스에서 더블클릭하면 바로 수정 가능
    """

    BLOCK_TYPE = "text"

    def __init__(self, position: tuple[float, float] = (0.0, 0.0), block_id: str | None = None) -> None:
        super().__init__(position=position, block_id=block_id)

        self._text: str = DEFAULT_TEXT
        self._bold: bool = False
        self._font_size: int = DEFAULT_FONT_SIZE

        self._editor: _InlineTextEditor | None = None  # 편집 중일 때만 존재

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)

    # --- 공개 API: 다른 코드(속성 패널, 파일 로더 등)가 서식을 바꿀 때 사용 ---

    def set_text(self, text: str) -> None:
        """텍스트 내용을 바꾸고 다시 그린다."""
        self._text = text
        self.prepareGeometryChange()
        self.update()

    def set_bold(self, bold: bool) -> None:
        """굵게 표시 여부를 바꾼다."""
        self._bold = bold
        self.prepareGeometryChange()
        self.update()

    def set_font_size(self, size: int) -> None:
        """글자 크기(pt)를 바꾼다."""
        self._font_size = size
        self.prepareGeometryChange()
        self.update()

    def text(self) -> str:
        """현재 텍스트 내용을 반환한다."""
        return self._text

    def is_bold(self) -> bool:
        """굵게 표시 중인지 반환한다 (속성 패널이 체크박스 초기값으로 사용)."""
        return self._bold

    def font_size(self) -> int:
        """현재 글자 크기(pt)를 반환한다."""
        return self._font_size

    def _font(self) -> QFont:
        """현재 서식(굵기/크기)이 반영된 QFont를 만든다."""
        font = QFont()
        font.setPointSize(self._font_size)
        font.setBold(self._bold)
        return font

    # --- QGraphicsItem 필수 구현 ---

    def boundingRect(self) -> QRectF:  # noqa: N802
        """현재 텍스트를 현재 폰트로 그렸을 때 필요한 사각형 영역."""
        metrics = QFontMetrics(self._font())
        text_rect = metrics.boundingRect(self._text or " ")
        width = max(text_rect.width() + TEXT_PADDING * 2, 40)
        height = max(text_rect.height() + TEXT_PADDING * 2, 24)
        return QRectF(0, 0, width, height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """편집 중이 아닐 때만 텍스트를 직접 그린다 (편집 중엔 _InlineTextEditor가 대신 보여줌)."""
        if self._editor is not None:
            return

        # OS가 다크 테마일 때 painter의 펜이 흰색을 물려받는 경우가 있어
        # 흰 배경(canvas/grid.py) 위에 글자가 안 보이는 문제가 생긴다.
        # 캔버스는 항상 종이처럼 밝게 유지할 것이므로 글자색을 검정으로 고정한다.
        painter.setPen(QColor(0, 0, 0))
        painter.setFont(self._font())
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)

        if self.isSelected():
            pen = painter.pen()
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.boundingRect())

    # --- 편집 모드 진입/종료 ---

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """더블클릭하면 편집 모드로 들어간다."""
        self.start_editing()
        event.accept()

    def start_editing(self) -> None:
        """
        인라인 편집기를 만들어 현재 텍스트를 채워 넣고 포커스를 준다.

        Note:
            편집 중에는 paint()가 아무것도 그리지 않으므로,
            화면에는 _InlineTextEditor만 보이게 되어 텍스트가 겹쳐 보이지 않는다.
        """
        if self._editor is not None:
            return

        self.update()
        self._editor = _InlineTextEditor(self)
        self._editor.setFont(self._font())
        self._editor.setDefaultTextColor(Qt.GlobalColor.black)
        self._editor.setPlainText(self._text)
        self._editor.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self._editor.setPos(0, 0)

        self._editor.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self._editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self._editor.setTextCursor(cursor)

    def finish_editing(self) -> None:
        """편집기 내용을 self._text로 확정하고 편집기를 없앤다."""
        if self._editor is None:
            return

        self.set_text(self._editor.toPlainText() or DEFAULT_TEXT)

        editor = self._editor
        self._editor = None  # paint()가 다시 그리기 시작하도록 먼저 None으로 만든다
        editor.setParentItem(None)
        if editor.scene() is not None:
            editor.scene().removeItem(editor)

        self.update()

    # --- 직렬화 ---

    def serialize(self) -> dict:
        """공통 필드(BaseBlock) + 텍스트 내용/서식을 함께 담는다."""
        data = super().serialize()
        data["content"] = self._text
        data["style"] = {"font_size": self._font_size, "bold": self._bold}
        return data

    def deserialize(self, data: dict) -> None:
        """저장된 dict로부터 위치 + 텍스트 내용/서식을 복원한다."""
        super().deserialize(data)
        self._text = data.get("content", DEFAULT_TEXT)
        style = data.get("style", {})
        self._font_size = style.get("font_size", DEFAULT_FONT_SIZE)
        self._bold = style.get("bold", False)
        self.update()
