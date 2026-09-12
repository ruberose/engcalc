"""
문서 캔버스를 화면에 보여주는 뷰 — QGraphicsView 서브클래스.

마우스 휠(기본) 스크롤 / Ctrl+휠 확대·축소, 휠 버튼(가운데 버튼) 드래그 또는
Space+드래그로 캔버스 패닝, Delete 키로 선택된 블록 삭제, 이미지 파일
드래그앤드롭 삽입을 담당한다. "그리기" 자체는 DocumentScene의 몫이고, 이
클래스는 사용자 입력을 어떻게 캔버스 조작으로 바꿀지만 다룬다.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsScene, QGraphicsTextItem, QGraphicsView

from blocks.image_block import SUPPORTED_EXTENSIONS

# --- 확대/축소 배율 ---
ZOOM_IN_FACTOR = 1.15
ZOOM_OUT_FACTOR = 1 / ZOOM_IN_FACTOR
MIN_SCALE = 0.1
MAX_SCALE = 5.0


class DocumentView(QGraphicsView):
    """
    DocumentScene을 보여주는 뷰.

    사용 예:
        view = DocumentView(scene)
        layout.addWidget(view)
    """

    def __init__(self, scene: QGraphicsScene, parent=None) -> None:
        super().__init__(scene, parent)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._current_scale: float = 1.0

        # 휠 버튼(가운데 버튼)을 누른 채 드래그하면 그 이동량만큼 스크롤바를
        # 직접 옮겨서 패닝한다(Qt의 ScrollHandDrag는 왼쪽 버튼 전용이라, 이건
        # 별도로 마우스 이벤트를 가로채 구현한다).
        self._panning: bool = False
        self._pan_last_pos = None

        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """탐색기에서 지원하는 이미지 파일을 끌고 오면 받아들일 준비를 한다."""
        if self._has_supported_image_url(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        """드래그 중에도 계속 받아들일 수 있음을 알려준다 (Qt 드래그앤드롭 규약)."""
        if self._has_supported_image_url(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """놓인 위치에 이미지 블록을 만든다."""
        scene = self.scene()
        if scene is None or not hasattr(scene, "create_image_block_from_file"):
            super().dropEvent(event)
            return

        image_paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile() and url.toLocalFile().lower().endswith(SUPPORTED_EXTENSIONS)
        ]
        if not image_paths:
            super().dropEvent(event)
            return

        scene_pos = self.mapToScene(event.position().toPoint())
        for offset, path in enumerate(image_paths):
            # 여러 파일을 한 번에 드롭하면 겹치지 않도록 조금씩 오른쪽 아래로 어긋나게 놓는다.
            pos = scene_pos + type(scene_pos)(offset * 20, offset * 20)
            scene.create_image_block_from_file(pos, path)

        event.acceptProposedAction()

    def _has_supported_image_url(self, event) -> bool:
        """드래그 중인 항목에 지원 형식의 로컬 이미지 파일이 하나라도 있는지 확인한다."""
        if not event.mimeData().hasUrls():
            return False
        return any(
            url.isLocalFile() and url.toLocalFile().lower().endswith(SUPPORTED_EXTENSIONS)
            for url in event.mimeData().urls()
        )

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Ctrl+휠: 커서 위치를 중심으로 확대/축소. 휠만 굴리면 기본 동작(위아래 스크롤)."""
        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            super().wheelEvent(event)
            return

        factor = ZOOM_IN_FACTOR if event.angleDelta().y() > 0 else ZOOM_OUT_FACTOR
        new_scale = self._current_scale * factor

        if new_scale < MIN_SCALE or new_scale > MAX_SCALE:
            return  # 너무 작아지거나 커지면 무시 (블록을 잃어버리지 않도록)

        self._current_scale = new_scale
        self.scale(factor, factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """휠 버튼(가운데 버튼)을 누르면 패닝을 시작한다."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_last_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """패닝 중이면 마우스가 움직인 만큼 스크롤바를 직접 옮긴다."""
        if self._panning and self._pan_last_pos is not None:
            delta = event.position() - self._pan_last_pos
            self._pan_last_pos = event.position()
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - round(delta.x()))
            v_bar.setValue(v_bar.value() - round(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """휠 버튼에서 손을 떼면 패닝을 끝낸다."""
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self._pan_last_pos = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """
        Space: 눌려있는 동안 드래그 스크롤(패닝) 모드로 전환.
        Delete/Backspace: 텍스트 편집 중이 아닐 때만 선택된 블록 삭제.
        """
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            return

        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # focusItem()이 실제 편집기(QGraphicsTextItem)일 때만 "텍스트 편집 중"이다.
            # (블록 자신도 클릭만으로 focusItem이 될 수 있어서, 단순히 focusItem이
            # 있는지 없는지만으로는 편집 중인지 판단할 수 없다.) 편집 중이면
            # Delete/Backspace가 "글자 지우기"로 쓰여야 하므로 블록 삭제를 하지 않는다.
            scene = self.scene()
            if scene is not None and not isinstance(scene.focusItem(), QGraphicsTextItem):
                self._delete_selected_blocks()
                return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Space에서 손을 떼면 다시 선택(러버밴드) 모드로 되돌린다."""
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            return
        super().keyReleaseEvent(event)

    def _delete_selected_blocks(self) -> None:
        """
        현재 선택된 모든 블록을 캔버스에서 제거한다.

        Note:
            삭제한 블록이 수식 블록이고 변수를 정의하고 있었다면, 그 변수를
            참조하던 다른 블록들은 재계산해주기 전까지 삭제 전 값을 그대로
            보여주게 된다("정의되지 않은 변수" 에러가 안 뜨고 옛날 값이 남음).
            그래서 삭제 후에는 항상 recalculate_all()로 전체를 다시 계산한다
            (변수 목록도 이걸 계기로 같이 갱신됨 - variables_changed 신호).
        """
        scene = self.scene()
        if scene is None:
            return
        selected = scene.selectedItems()
        if not selected:
            return
        before = scene.capture_undo_snapshot() if hasattr(scene, "capture_undo_snapshot") else None
        for item in selected:
            scene.removeItem(item)
        if before is not None and hasattr(scene, "commit_undo_snapshot"):
            scene.commit_undo_snapshot(before)
        if hasattr(scene, "recalculate_all"):
            scene.recalculate_all()
