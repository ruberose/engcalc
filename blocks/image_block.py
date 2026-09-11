"""
이미지 블록 — 캔버스에 그림(단면도, 배치도 등)을 삽입한다.

PNG/JPG/BMP는 QPixmap이 바로 읽고, SVG는 QSvgRenderer로 한 번 래스터화해서
QPixmap으로 바꿔둔다 — 그래야 그리기(paint)/크기 조절/직렬화 로직을
포맷과 무관하게 하나로 통일할 수 있다 (벡터 확대 시 무한히 선명하진
않지만, 1차 범위에서는 충분하다).

우측 하단의 작은 정사각형을 드래그하면 크기를 조절할 수 있다.
"""

import base64

from PySide6.QtCore import QBuffer, QIODevice, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from blocks.base_block import BaseBlock

#: 파일 선택 대화상자 등에서 사용할, 이 블록이 지원하는 확장자 목록.
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".svg")

_HANDLE_SIZE = 12.0
_MIN_SIZE = 20.0
_PLACEHOLDER_TEXT = "이미지를 불러올 수 없음"


def load_pixmap_from_file(file_path: str) -> QPixmap:
    """
    이미지 파일을 읽어 QPixmap으로 반환한다.

    Args:
        file_path: PNG/JPG/BMP/SVG 파일 경로

    Returns:
        불러온 이미지. 실패하면 null pixmap(isNull()==True)을 반환한다 —
        호출하는 쪽이 이를 보고 "이미지 없음" 상태로 처리하면 되므로,
        여기서는 예외를 앱 밖으로 던지지 않는다.

    Note:
        SVG는 QPixmap이 직접 읽을 수 없어서, QSvgRenderer로 그린 뒤
        원본 크기의 2배 해상도로 래스터화한다 (확대했을 때 덜 흐릿하도록).
    """
    if file_path.lower().endswith(".svg"):
        renderer = QSvgRenderer(file_path)
        if not renderer.isValid():
            return QPixmap()
        size = renderer.defaultSize()
        if size.isEmpty():
            size = QSize(200, 150)
        target_size = QSize(size.width() * 2, size.height() * 2)

        pixmap = QPixmap(target_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap

    return QPixmap(file_path)


class ImageBlock(BaseBlock):
    """
    이미지 블록.

    사용 예:
        pixmap = load_pixmap_from_file("section.png")
        block = ImageBlock(position=(100, 300), pixmap=pixmap)
        scene.addItem(block)
        # 블록을 선택한 뒤 우측 하단 손잡이를 드래그하면 크기 조절
    """

    BLOCK_TYPE = "image"

    def __init__(
        self,
        position: tuple[float, float] = (0.0, 0.0),
        pixmap: QPixmap | None = None,
        caption: str = "",
        block_id: str | None = None,
    ) -> None:
        super().__init__(position=position, block_id=block_id)

        self._pixmap = pixmap if pixmap is not None else QPixmap()
        self._caption = caption

        if not self._pixmap.isNull():
            self._width = float(self._pixmap.width())
            self._height = float(self._pixmap.height())
        else:
            self._width, self._height = 200.0, 150.0

        self._resizing = False
        self._resize_start_mouse = None
        self._resize_start_size = (0.0, 0.0)
        self._undo_snapshot_before_resize: list[dict] | None = None

    def set_size(self, width: float, height: float) -> None:
        """
        블록 크기를 지정한다.

        Note:
            우측 하단 손잡이 드래그(mouseMoveEvent)와 속성 패널 입력, 두 경로 모두
            결국 이 메서드가 하는 것과 같은 일(폭/높이 갱신 + 다시 그리기)을 하므로,
            속성 패널은 이 공개 메서드를 통해서만 크기를 바꾼다.
        """
        self.prepareGeometryChange()
        self._width = max(_MIN_SIZE, width)
        self._height = max(_MIN_SIZE, height)
        self.update()

    def caption(self) -> str:
        """이미지 캡션을 반환한다."""
        return self._caption

    # --- QGraphicsItem 필수 구현 ---

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(0, 0, self._width, self._height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        rect = self.boundingRect()

        if self._pixmap.isNull():
            painter.fillRect(rect, QColor(235, 235, 235))
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, _PLACEHOLDER_TEXT)
        else:
            painter.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))

        if self.isSelected():
            pen = QPen(QColor(0, 0, 0))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setBrush(QColor(255, 255, 255))
            painter.drawRect(self._handle_rect())

    def _handle_rect(self) -> QRectF:
        """우측 하단 크기 조절 손잡이의 사각형 (씬이 아닌 이 블록의 로컬 좌표계 기준)."""
        return QRectF(self._width - _HANDLE_SIZE, self._height - _HANDLE_SIZE, _HANDLE_SIZE, _HANDLE_SIZE)

    # --- 크기 조절 ---

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """
        선택된 상태에서 우측 하단 손잡이를 누르면 크기 조절 모드로 들어간다.

        Note:
            손잡이가 아닌 곳을 누르면 그냥 super()에 맡긴다 — BaseBlock이 설정한
            ItemIsMovable 플래그 덕분에 Qt가 알아서 드래그 이동을 처리해준다.
        """
        if self.isSelected() and self._handle_rect().contains(event.pos()):
            self._resizing = True
            self._resize_start_mouse = event.scenePos()
            self._resize_start_size = (self._width, self._height)
            scene = self.scene()
            self._undo_snapshot_before_resize = (
                scene.capture_undo_snapshot() if scene is not None and hasattr(scene, "capture_undo_snapshot") else None
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._resizing and self._resize_start_mouse is not None:
            delta = event.scenePos() - self._resize_start_mouse
            start_w, start_h = self._resize_start_size
            self.set_size(start_w + delta.x(), start_h + delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._resizing:
            self._resizing = False
            self._resize_start_mouse = None
            scene = self.scene()
            if scene is not None and self._undo_snapshot_before_resize is not None and hasattr(scene, "commit_undo_snapshot"):
                scene.commit_undo_snapshot(self._undo_snapshot_before_resize)
            self._undo_snapshot_before_resize = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # --- 직렬화 ---

    def serialize(self) -> dict:
        """공통 필드(BaseBlock) + 이미지 데이터(base64 PNG)/크기/캡션을 담는다."""
        data = super().serialize()
        data["size"] = [self._width, self._height]
        data["image_data"] = _pixmap_to_base64(self._pixmap)
        data["caption"] = self._caption
        return data

    def deserialize(self, data: dict) -> None:
        """저장된 dict로부터 위치/크기/이미지/캡션을 복원한다."""
        super().deserialize(data)
        width, height = data.get("size", [200.0, 150.0])
        self.prepareGeometryChange()
        self._width, self._height = float(width), float(height)
        image_data = data.get("image_data", "")
        self._pixmap = _pixmap_from_base64(image_data) if image_data else QPixmap()
        self._caption = data.get("caption", "")
        self.update()


def _pixmap_to_base64(pixmap: QPixmap) -> str:
    """QPixmap을 PNG로 인코딩한 뒤 base64 문자열로 바꾼다 (JSON에 담기 위함)."""
    if pixmap.isNull():
        return ""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return base64.b64encode(bytes(buffer.data())).decode("ascii")


def _pixmap_from_base64(encoded: str) -> QPixmap:
    """base64 문자열(PNG)을 QPixmap으로 되돌린다."""
    pixmap = QPixmap()
    try:
        raw = base64.b64decode(encoded)
    except (ValueError, TypeError):
        return pixmap
    pixmap.loadFromData(raw, "PNG")
    return pixmap
