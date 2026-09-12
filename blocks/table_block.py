"""
표(테이블) 블록 — 단면 제원표, 하중 조합표처럼 행/열로 정리된 값을 담는다.

계산 기능은 없는 순수 텍스트 표다(숫자를 계산하려면 수식 블록을 따로 써서
결과를 표에 옮겨 적으면 된다). TextBlock/MathBlock과 같은 패턴으로 동작한다:
평소에는 격자와 각 칸의 글자를 직접 그리다가(paint), 칸을 더블클릭하면 그
칸 자리에만 작은 QGraphicsTextItem을 덧씌워 편집시키고, 편집이 끝나면
그 칸의 글자로 다시 흡수한다.

행/열은 두 가지 방법으로 늘리거나 줄일 수 있다:
    - 칸을 더블클릭해 편집 중이 아닐 때 오른쪽 클릭 -> 우클릭 메뉴(행/열
      추가·삭제, 마지막으로 클릭한 칸 기준)
    - 속성 패널의 "행 수"/"열 수" 입력(맨 끝에 추가/삭제, ui/property_panel.py)
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneContextMenuEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QMenu,
    QStyleOptionGraphicsItem,
    QWidget,
)

from blocks.base_block import BaseBlock

# --- 표 기본 서식 ---
DEFAULT_FONT_SIZE = 12
DEFAULT_ROWS = 3
DEFAULT_COLS = 3
CELL_PADDING_X = 8.0
CELL_PADDING_Y = 6.0
MIN_CELL_WIDTH = 48.0
MIN_CELL_HEIGHT = 24.0

_GRID_LINE_COLOR = QColor(150, 150, 150)
_TEXT_COLOR = QColor(0, 0, 0)


class _InlineCellEditor(QGraphicsTextItem):
    """TableBlock이 칸 편집 모드일 때만 잠깐 만들어지는 편집 위젯 (TextBlock의 편집기와 같은 패턴)."""

    def __init__(self, parent_block: "TableBlock") -> None:
        super().__init__(parent_block)
        self._parent_block = parent_block

    def focusOutEvent(self, event) -> None:  # noqa: N802
        """편집창 밖을 클릭하는 등 포커스를 잃으면 편집을 마무리한다."""
        super().focusOutEvent(event)
        self._parent_block.finish_cell_editing()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Enter로 편집을 끝내고, Tab이면 편집을 끝낸 뒤 바로 다음 칸 편집으로 이어간다."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._parent_block.finish_cell_editing()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Tab:
            self._parent_block.finish_cell_editing(move_to_next=True)
            event.accept()
            return
        super().keyPressEvent(event)


class TableBlock(BaseBlock):
    """
    표 블록.

    사용 예:
        block = TableBlock(position=(100, 200), rows=3, cols=2)
        block.set_cell_text(0, 0, "부재")
        block.set_cell_text(0, 1, "단면적(mm^2)")
        scene.addItem(block)
        # 칸을 더블클릭하면 바로 그 칸만 편집 가능. 우클릭하면 행/열 추가·삭제 메뉴.
    """

    BLOCK_TYPE = "table"

    def __init__(
        self,
        position: tuple[float, float] = (0.0, 0.0),
        rows: int = DEFAULT_ROWS,
        cols: int = DEFAULT_COLS,
        block_id: str | None = None,
    ) -> None:
        super().__init__(position=position, block_id=block_id)

        rows = max(1, rows)
        cols = max(1, cols)
        self._cells: list[list[str]] = [["" for _ in range(cols)] for _ in range(rows)]
        self._font_size: int = DEFAULT_FONT_SIZE

        #: 마지막으로 클릭/편집한 칸 — 우클릭 메뉴의 행/열 추가·삭제 기준점.
        self._active_cell: tuple[int, int] = (0, 0)
        self._editor: _InlineCellEditor | None = None
        self._editing_cell: tuple[int, int] | None = None
        self._undo_snapshot_before_edit: list[dict] | None = None

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)

    # --- 공개 API: 칸 내용 ---

    def row_count(self) -> int:
        """행 개수."""
        return len(self._cells)

    def col_count(self) -> int:
        """열 개수."""
        return len(self._cells[0]) if self._cells else 0

    def cell_text(self, row: int, col: int) -> str:
        """(row, col) 칸의 내용."""
        return self._cells[row][col]

    def set_cell_text(self, row: int, col: int, text: str) -> None:
        """(row, col) 칸의 내용을 바꾸고 다시 그린다."""
        self.prepareGeometryChange()
        self._cells[row][col] = text
        self.update()

    def font_size(self) -> int:
        """현재 글자 크기(pt)를 반환한다."""
        return self._font_size

    def set_font_size(self, size: int) -> None:
        """글자 크기(pt)를 바꾸고(칸 크기도 그에 맞춰 다시 계산됨) 다시 그린다."""
        self.prepareGeometryChange()
        self._font_size = size
        self.update()

    # --- 공개 API: 행/열 추가·삭제 ---
    # add_row/remove_row/add_col/remove_col은 우클릭 메뉴가 "마지막으로 클릭한
    # 칸 기준으로" 삽입/삭제할 때 쓰고, set_row_count/set_col_count는 속성
    # 패널이 "끝에 몇 개 더/덜"로 조절할 때 쓴다 — 용도가 달라 함께 남겨둔다.

    def add_row(self, after: int | None = None) -> None:
        """after행 바로 다음에 빈 행을 추가한다 (생략하면 마지막으로 클릭한 칸의 행 기준)."""
        index = (after if after is not None else self._active_cell[0]) + 1
        index = max(0, min(index, self.row_count()))
        self.prepareGeometryChange()
        self._cells.insert(index, ["" for _ in range(self.col_count())])
        self.update()

    def remove_row(self, index: int | None = None) -> None:
        """index행을 지운다 (생략하면 마지막으로 클릭한 칸의 행 기준). 마지막 남은 한 행은 지울 수 없다."""
        if self.row_count() <= 1:
            return
        index = index if index is not None else self._active_cell[0]
        index = max(0, min(index, self.row_count() - 1))
        self.prepareGeometryChange()
        del self._cells[index]
        row, col = self._active_cell
        self._active_cell = (max(0, min(row, self.row_count() - 1)), col)
        self.update()

    def add_col(self, after: int | None = None) -> None:
        """after열 바로 다음에 빈 열을 추가한다 (생략하면 마지막으로 클릭한 칸의 열 기준)."""
        index = (after if after is not None else self._active_cell[1]) + 1
        index = max(0, min(index, self.col_count()))
        self.prepareGeometryChange()
        for row in self._cells:
            row.insert(index, "")
        self.update()

    def remove_col(self, index: int | None = None) -> None:
        """index열을 지운다 (생략하면 마지막으로 클릭한 칸의 열 기준). 마지막 남은 한 열은 지울 수 없다."""
        if self.col_count() <= 1:
            return
        index = index if index is not None else self._active_cell[1]
        index = max(0, min(index, self.col_count() - 1))
        self.prepareGeometryChange()
        for row in self._cells:
            del row[index]
        row_idx, col = self._active_cell
        self._active_cell = (row_idx, max(0, min(col, self.col_count() - 1)))
        self.update()

    def set_row_count(self, count: int) -> None:
        """행 개수를 count로 맞춘다 — 늘어나면 끝에 빈 행을, 줄어들면 끝에서부터 지운다."""
        count = max(1, count)
        self.prepareGeometryChange()
        while self.row_count() < count:
            self._cells.append(["" for _ in range(self.col_count())])
        while self.row_count() > count:
            del self._cells[-1]
        self.update()

    def set_col_count(self, count: int) -> None:
        """열 개수를 count로 맞춘다 — 늘어나면 끝에 빈 열을, 줄어들면 끝에서부터 지운다."""
        count = max(1, count)
        self.prepareGeometryChange()
        for row in self._cells:
            while len(row) < count:
                row.append("")
            while len(row) > count:
                del row[-1]
        self.update()

    # --- 칸 레이아웃 계산 ---

    def _font(self) -> QFont:
        font = QFont()
        font.setPointSize(self._font_size)
        return font

    def _column_widths(self, metrics: QFontMetrics) -> list[float]:
        """각 열의 폭 — 그 열에서 가장 넓은 칸 글자에 맞춘다."""
        widths = []
        for col in range(self.col_count()):
            widest = max((metrics.horizontalAdvance(self._cells[row][col]) for row in range(self.row_count())), default=0)
            widths.append(max(widest + CELL_PADDING_X * 2, MIN_CELL_WIDTH))
        return widths

    def _row_height(self, metrics: QFontMetrics) -> float:
        """모든 행이 공유하는 행 높이 — 한 줄 표시만 지원한다(줄바꿈 없음)."""
        return max(metrics.height() + CELL_PADDING_Y * 2, MIN_CELL_HEIGHT)

    def _cell_rect(self, row: int, col: int) -> QRectF:
        """(row, col) 칸의 사각형 (이 블록의 로컬 좌표계 기준)."""
        metrics = QFontMetrics(self._font())
        widths = self._column_widths(metrics)
        row_h = self._row_height(metrics)
        x = sum(widths[:col])
        return QRectF(x, row_h * row, widths[col], row_h)

    def _cell_at(self, pos: QPointF) -> tuple[int, int] | None:
        """씬이 아닌 이 블록의 로컬 좌표 pos가 어느 칸 위인지 찾는다. 표 바깥이면 None."""
        metrics = QFontMetrics(self._font())
        widths = self._column_widths(metrics)
        row_h = self._row_height(metrics)

        if pos.x() < 0 or pos.y() < 0:
            return None
        row = int(pos.y() // row_h)
        if row >= self.row_count():
            return None

        x = 0.0
        for col, width in enumerate(widths):
            if x <= pos.x() < x + width:
                return row, col
            x += width
        return None

    # --- QGraphicsItem 필수 구현 ---

    def boundingRect(self) -> QRectF:  # noqa: N802
        metrics = QFontMetrics(self._font())
        widths = self._column_widths(metrics)
        row_h = self._row_height(metrics)
        width = max(sum(widths), MIN_CELL_WIDTH)
        height = max(row_h * self.row_count(), MIN_CELL_HEIGHT)
        return QRectF(0, 0, width, height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        metrics = QFontMetrics(self._font())
        widths = self._column_widths(metrics)
        row_h = self._row_height(metrics)
        total_width = sum(widths)
        total_height = row_h * self.row_count()

        painter.setFont(self._font())
        painter.setPen(_TEXT_COLOR)
        y = 0.0
        for row in range(self.row_count()):
            x = 0.0
            for col in range(self.col_count()):
                width = widths[col]
                if self._editing_cell != (row, col):
                    rect = QRectF(x + CELL_PADDING_X, y, width - CELL_PADDING_X * 2, row_h)
                    painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._cells[row][col])
                x += width
            y += row_h

        painter.setPen(_GRID_LINE_COLOR)
        x = 0.0
        for width in widths:
            painter.drawLine(round(x), 0, round(x), round(total_height))
            x += width
        painter.drawLine(round(total_width), 0, round(total_width), round(total_height))
        y = 0.0
        for _ in range(self.row_count() + 1):
            painter.drawLine(0, round(y), round(total_width), round(y))
            y += row_h

        if self.isSelected():
            pen = QPen(self._selection_pen_color())
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())

        self._draw_lock_badge(painter, self.boundingRect())

    # --- 칸 선택 / 편집 모드 ---

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """클릭한 칸을 "마지막으로 클릭한 칸"으로 기억해둔다(우클릭 메뉴의 기준점) — 이동/선택 자체는 BaseBlock에 맡긴다."""
        cell = self._cell_at(event.pos())
        if cell is not None:
            self._active_cell = cell
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """더블클릭한 칸의 편집 모드로 들어간다."""
        cell = self._cell_at(event.pos())
        if cell is not None:
            self.start_cell_editing(cell)
        event.accept()

    def start_cell_editing(self, cell: tuple[int, int], undo_snapshot: list[dict] | None = None) -> None:
        """
        지정한 칸 위에 인라인 편집기를 만들어 그 칸의 내용을 채워 넣고 포커스를 준다.

        Args:
            cell: (row, col)
            undo_snapshot: 이미 캡처해둔 "편집 시작 전" 상태가 있으면 그걸 그대로 쓴다
                (Tab으로 다음 칸 편집을 이어갈 때는 새로 캡처하지 않고 이전 칸 편집의
                스냅샷을 그대로 이어받는다 — finish_cell_editing 참고).
        """
        if self._locked:
            return
        if self._editor is not None:
            return

        row, col = cell
        self._active_cell = cell
        self._editing_cell = cell

        scene = self.scene()
        if undo_snapshot is not None:
            self._undo_snapshot_before_edit = undo_snapshot
        elif scene is not None and hasattr(scene, "capture_undo_snapshot"):
            self._undo_snapshot_before_edit = scene.capture_undo_snapshot()
        else:
            self._undo_snapshot_before_edit = None

        self.update()
        rect = self._cell_rect(row, col)
        metrics = QFontMetrics(self._font())

        self._editor = _InlineCellEditor(self)
        self._editor.setFont(self._font())
        self._editor.setDefaultTextColor(Qt.GlobalColor.black)
        self._editor.setPlainText(self._cells[row][col])
        self._editor.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self._editor.setPos(rect.x(), rect.y() + (rect.height() - metrics.height()) / 2)

        self._editor.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self._editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self._editor.setTextCursor(cursor)

    def finish_cell_editing(self, move_to_next: bool = False) -> None:
        """
        편집기 내용을 그 칸의 값으로 확정한다.

        Args:
            move_to_next: True면(Tab 입력) 확정 직후 바로 다음 칸(오른쪽, 마지막
                열이면 다음 행 첫 칸) 편집으로 이어간다 — 표를 채울 때 매번
                더블클릭하지 않고 Tab만으로 쭉 입력할 수 있게 하기 위함이다.
        """
        if self._editor is None:
            return

        row, col = self._editing_cell
        text = self._editor.toPlainText()

        editor = self._editor
        self._editor = None  # paint()가 이 칸을 다시 그리기 시작하도록 먼저 None으로 만든다
        self._editing_cell = None
        editor.setParentItem(None)
        if editor.scene() is not None:
            editor.scene().removeItem(editor)

        self.prepareGeometryChange()
        self._cells[row][col] = text
        self.update()

        snapshot = self._undo_snapshot_before_edit
        self._undo_snapshot_before_edit = None

        if move_to_next:
            next_row, next_col = row, col + 1
            if next_col >= self.col_count():
                next_row, next_col = row + 1, 0
            if next_row < self.row_count():
                self.start_cell_editing((next_row, next_col), undo_snapshot=snapshot)
                return  # 다음 칸 편집이 이어지므로, 실행취소 기록은 그 편집이 끝날 때 한 번에 남긴다

        scene = self.scene()
        if snapshot is not None and scene is not None and hasattr(scene, "commit_undo_snapshot"):
            scene.commit_undo_snapshot(snapshot)

    # --- 우클릭 메뉴: 행/열 추가·삭제 ---

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:  # noqa: N802
        """마지막으로 클릭한(또는 지금 우클릭한) 칸을 기준으로 행/열을 추가·삭제하는 메뉴를 띄운다."""
        if self._locked:
            event.ignore()
            return

        cell = self._cell_at(event.pos())
        if cell is not None:
            self._active_cell = cell

        menu = QMenu()
        add_row_action = menu.addAction("행 추가 (아래)")
        remove_row_action = menu.addAction("행 삭제")
        remove_row_action.setEnabled(self.row_count() > 1)
        menu.addSeparator()
        add_col_action = menu.addAction("열 추가 (오른쪽)")
        remove_col_action = menu.addAction("열 삭제")
        remove_col_action.setEnabled(self.col_count() > 1)

        chosen = menu.exec(event.screenPos())
        if chosen is None:
            return

        scene = self.scene()
        before = scene.capture_undo_snapshot() if scene is not None and hasattr(scene, "capture_undo_snapshot") else None

        if chosen is add_row_action:
            self.add_row()
        elif chosen is remove_row_action:
            self.remove_row()
        elif chosen is add_col_action:
            self.add_col()
        elif chosen is remove_col_action:
            self.remove_col()

        if before is not None and scene is not None and hasattr(scene, "commit_undo_snapshot"):
            scene.commit_undo_snapshot(before)

    # --- 직렬화 ---

    def serialize(self) -> dict:
        """공통 필드(BaseBlock) + 칸 내용(행 x 열) + 글자 크기를 담는다."""
        data = super().serialize()
        data["cells"] = [list(row) for row in self._cells]
        data["font_size"] = self._font_size
        return data

    def deserialize(self, data: dict) -> None:
        """저장된 dict로부터 위치 + 칸 내용 + 글자 크기를 복원한다."""
        super().deserialize(data)
        cells = data.get("cells") or [["" for _ in range(DEFAULT_COLS)] for _ in range(DEFAULT_ROWS)]
        self.prepareGeometryChange()
        self._cells = [list(row) for row in cells]
        self._font_size = data.get("font_size", DEFAULT_FONT_SIZE)
        self._active_cell = (0, 0)
        self.update()
