"""
텍스트 블록.

캔버스 위에서 제목·설명 등 자유 서식 텍스트를 표시하는 블록.
평소에는 자신이 직접 텍스트를 그리다가(paint), 더블클릭하면
편집용 QGraphicsTextItem을 잠깐 덧씌워서 편집시키고, 편집이 끝나면
그 내용을 다시 자기 것으로 흡수하는 방식으로 동작한다.

위첨자/아래첨자는 "^{내용}"/"_{내용}" 마크업으로 쓴다 (예: "x^{2}",
"sigma_{허용}"). MathBlock의 수식 표기(^, _)와 같은 관례라 외우기 쉽고,
mathtext처럼 ASCII만 되는 제약 없이 한글도 위/아래첨자로 쓸 수 있다.
"""

import re

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

# --- 위첨자/아래첨자 ---
# "^{...}" -> 위첨자, "_{...}" -> 아래첨자. 중괄호 안에는 { } 를 직접 못 넣는다
# (여러 글자를 한 번에 위/아래첨자로 묶어 쓰기 위한 것이라 이 정도 제약은 괜찮음).
_SCRIPT_PATTERN = re.compile(r"\^\{([^{}]*)\}|_\{([^{}]*)\}")
_SCRIPT_FONT_SCALE = 0.65  # 위/아래첨자 글자 크기 비율 (본문 대비)
_SUPERSCRIPT_RAISE_RATIO = 0.35  # 본문 줄 높이 대비, 위로 띄우는 비율
_SUBSCRIPT_LOWER_RATIO = 0.15  # 본문 줄 높이 대비, 아래로 내리는 비율


def _tokenize_script_markup(text: str) -> list[tuple[str, str]]:
    """
    "x^{2} + y_{허용}" 같은 텍스트를 (종류, 내용) 토큰 리스트로 쪼갠다.

    종류는 "normal"(보통 글자), "super"(위첨자), "sub"(아래첨자) 중 하나.
    빈 문자열을 넣으면 [("normal", "")] 하나를 돌려준다(빈 줄도 자리는 차지해야 하므로).
    """
    tokens: list[tuple[str, str]] = []
    pos = 0
    for match in _SCRIPT_PATTERN.finditer(text):
        if match.start() > pos:
            tokens.append(("normal", text[pos : match.start()]))
        super_text, sub_text = match.groups()
        tokens.append(("super", super_text) if super_text is not None else ("sub", sub_text))
        pos = match.end()
    if pos < len(text) or not tokens:
        tokens.append(("normal", text[pos:]))
    return tokens


class _InlineTextEditor(QGraphicsTextItem):
    """
    TextBlock이 편집 모드일 때만 잠깐 만들어지는 실제 편집 위젯.

    QGraphicsTextItem은 자체적으로 커서·선택·IME 입력을 다 처리해주므로,
    편집 UI를 직접 구현하는 대신 이 표준 위젯을 빌려 쓰고,
    포커스를 잃는 순간(focusOutEvent) 부모 TextBlock에게 "편집 끝났다"고 알려준다.

    편집 중에는 "x^{2}" 같은 마크업을 있는 그대로(가공 없이) 보여준다 —
    미리보기 없이 원문을 직접 타이핑하는 게, 어떤 마크업이 뭘 만드는지
    가장 명확하게 보여주는 방법이라고 판단했다.
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
        평상시: paint()가 self._text를 해석해서 직접 그림 (가볍고 빠름).
                "^{...}"/"_{...}" 마크업은 위/아래첨자로 그려진다.
        편집 중: _InlineTextEditor 자식 아이템이 화면을 덮고 원문 그대로 입력을 받음

    사용 예:
        block = TextBlock(position=(100, 50))
        block.set_text("sigma_{허용} = 24 MPa")   # "허용"이 아래첨자로 표시됨
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
        self._undo_snapshot_before_edit: list[dict] | None = None

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
        """현재 텍스트 내용을 반환한다 (위/아래첨자 마크업이 포함된 원문)."""
        return self._text

    def is_bold(self) -> bool:
        """굵게 표시 중인지 반환한다 (속성 패널이 체크박스 초기값으로 사용)."""
        return self._bold

    def font_size(self) -> int:
        """현재 글자 크기(pt)를 반환한다."""
        return self._font_size

    def _font(self) -> QFont:
        """현재 서식(굵기/크기)이 반영된 본문용 QFont를 만든다."""
        font = QFont()
        font.setPointSize(self._font_size)
        font.setBold(self._bold)
        return font

    def _script_font(self) -> QFont:
        """위/아래첨자용 QFont — 본문보다 작다(굵기는 본문과 맞춤)."""
        font = QFont()
        font.setPointSize(max(6, round(self._font_size * _SCRIPT_FONT_SCALE)))
        font.setBold(self._bold)
        return font

    def _layout(self) -> tuple[float, float, list[tuple[float, float, QFont, str]]]:
        """
        현재 텍스트(위/아래첨자 마크업 포함)를 해석해서 그리기 좋은 형태로 만든다.

        Returns:
            (전체 너비, 전체 높이, [(x, y, 폰트, 글자) ...]) — y는 이 블록의
            로컬 좌표계에서 각 조각을 그릴 베이스라인 위치(TEXT_PADDING 더하기 전).
        """
        font_normal = self._font()
        font_script = self._script_font()
        metrics_normal = QFontMetrics(font_normal)
        metrics_script = QFontMetrics(font_script)

        baseline = float(metrics_normal.ascent())
        min_top = baseline - metrics_normal.ascent()
        max_bottom = baseline + metrics_normal.descent()

        raw_segments: list[tuple[float, float, QFont, str]] = []
        x = 0.0
        for kind, content in _tokenize_script_markup(self._text or " "):
            if kind == "normal":
                raw_segments.append((x, baseline, font_normal, content))
                min_top = min(min_top, baseline - metrics_normal.ascent())
                max_bottom = max(max_bottom, baseline + metrics_normal.descent())
                x += metrics_normal.horizontalAdvance(content)
                continue

            if kind == "super":
                y = baseline - metrics_normal.height() * _SUPERSCRIPT_RAISE_RATIO
            else:  # "sub"
                y = baseline + metrics_normal.height() * _SUBSCRIPT_LOWER_RATIO
            raw_segments.append((x, y, font_script, content))
            min_top = min(min_top, y - metrics_script.ascent())
            max_bottom = max(max_bottom, y + metrics_script.descent())
            x += metrics_script.horizontalAdvance(content)

        width = max(x, 1.0)
        height = max_bottom - min_top

        # min_top이 음수면(위첨자가 원래 글자 위로 삐져나간 경우) 전부 아래로
        # 밀어서 y가 항상 0 이상이 되게 한다 — boundingRect가 실제로 그려지는
        # 영역을 전부 담도록 하기 위함.
        shift = -min_top
        segments = [(sx, sy + shift, sf, st) for sx, sy, sf, st in raw_segments]
        return width, height, segments

    # --- QGraphicsItem 필수 구현 ---

    def boundingRect(self) -> QRectF:  # noqa: N802
        """현재 텍스트를 현재 폰트로 그렸을 때 필요한 사각형 영역."""
        width, height, _segments = self._layout()
        total_width = max(width + TEXT_PADDING * 2, 40)
        total_height = max(height + TEXT_PADDING * 2, 24)
        return QRectF(0, 0, total_width, total_height)

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
        _width, _height, segments = self._layout()
        for x, y, font, content in segments:
            painter.setFont(font)
            painter.drawText(TEXT_PADDING + x, TEXT_PADDING + y, content)

        if self.isSelected():
            pen = painter.pen()
            pen.setColor(QColor(0, 0, 0))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.boundingRect())

    # --- 편집 모드 진입/종료 ---

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """더블클릭하면 편집 모드로 들어간다."""
        self.start_editing()
        event.accept()

    def start_editing(self, undo_snapshot: list[dict] | None = None) -> None:
        """
        인라인 편집기를 만들어 현재 텍스트를 채워 넣고 포커스를 준다.

        Args:
            undo_snapshot: 이미 캡처해둔 "편집 시작 전" 상태가 있으면 그걸 그대로 쓴다
                (예: 방금 만들어진 블록 — DocumentScene._create_text_block 참고).
                생략하면 지금 이 시점 기준으로 새로 캡처한다(기존 블록을 더블클릭해서
                편집하는 일반적인 경우).

        Note:
            편집 중에는 paint()가 아무것도 그리지 않으므로,
            화면에는 _InlineTextEditor만 보이게 되어 텍스트가 겹쳐 보이지 않는다.
        """
        if self._editor is not None:
            return

        scene = self.scene()
        if undo_snapshot is not None:
            self._undo_snapshot_before_edit = undo_snapshot
        elif scene is not None and hasattr(scene, "capture_undo_snapshot"):
            self._undo_snapshot_before_edit = scene.capture_undo_snapshot()
        else:
            self._undo_snapshot_before_edit = None

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

        # 실제로 뭔가 달라졌을 때만 commit_undo_snapshot() 내부에서 기록된다
        # (아무 내용도 안 바꾸고 편집만 들어갔다 나오면 실행취소 기록이 늘지 않는다).
        scene = self.scene()
        if self._undo_snapshot_before_edit is not None and scene is not None and hasattr(scene, "commit_undo_snapshot"):
            scene.commit_undo_snapshot(self._undo_snapshot_before_edit)
        self._undo_snapshot_before_edit = None

    # --- 직렬화 ---

    def serialize(self) -> dict:
        """공통 필드(BaseBlock) + 텍스트 내용(마크업 포함)/서식을 함께 담는다."""
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
