"""
문서 캔버스를 화면에 보여주는 뷰 — QGraphicsView 서브클래스.

마우스 휠 확대/축소, Space+드래그로 캔버스 스크롤(패닝), Delete 키로
선택된 블록 삭제 기능을 담당한다. "그리기" 자체는 DocumentScene의 몫이고,
이 클래스는 사용자 입력(휠, 키보드)을 어떻게 캔버스 조작으로 바꿀지만 다룬다.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

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

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """마우스 휠로 커서 위치를 중심으로 확대/축소한다."""
        factor = ZOOM_IN_FACTOR if event.angleDelta().y() > 0 else ZOOM_OUT_FACTOR
        new_scale = self._current_scale * factor

        if new_scale < MIN_SCALE or new_scale > MAX_SCALE:
            return  # 너무 작아지거나 커지면 무시 (블록을 잃어버리지 않도록)

        self._current_scale = new_scale
        self.scale(factor, factor)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """
        Space: 눌려있는 동안 드래그 스크롤(패닝) 모드로 전환.
        Delete/Backspace: 텍스트 편집 중이 아닐 때만 선택된 블록 삭제.
        """
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            return

        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # 씬의 focusItem()이 있다는 것은 텍스트 블록이 편집 중이라는 뜻이다.
            # 그럴 땐 Delete/Backspace가 "글자 지우기"로 쓰여야 하므로 블록 삭제를 하지 않는다.
            if self.scene() is not None and self.scene().focusItem() is None:
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
        """현재 선택된 모든 블록을 캔버스에서 제거한다."""
        scene = self.scene()
        if scene is None:
            return
        for item in scene.selectedItems():
            scene.removeItem(item)
