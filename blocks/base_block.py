"""
모든 블록 타입의 공통 부모 클래스.

캔버스 위에 올라가는 모든 요소(텍스트, 수식, 이미지 등)는 BaseBlock을 상속해서
이동·선택·삭제를 QGraphicsItem 기본 기능으로 공짜로 얻고,
저장/불러오기를 위한 serialize()/deserialize() 인터페이스만 각자 구현하면 된다.

블록끼리는 서로 직접 참조하지 않는다 (예: TextBlock이 MathBlock을 알지 못한다).
블록 간 소통이 필요해지면(Phase 2의 변수 참조 등) 캔버스/씬을 매개로
이벤트나 시그널을 통해 처리한다.
"""

import uuid

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

#: 선택 테두리 색 — 잠긴 블록은 회색으로 구분해서 "손댈 수 없음"을 알려준다.
_SELECTION_COLOR = QColor(0, 0, 0)
_SELECTION_COLOR_LOCKED = QColor(150, 150, 150)
#: 잠긴 블록 우측 상단에 그리는 작은 자물쇠 배지.
_LOCK_BADGE_SIZE = 16.0
_LOCK_BADGE_COLOR = QColor(120, 120, 120)


class BaseBlock(QGraphicsItem):
    """
    캔버스 위 모든 블록의 부모 클래스.

    제공하는 것:
        - 고유 id 자동 생성 (block_id를 주지 않으면 "blk_xxxxxxxx" 형태로 생성)
        - 이동/선택 가능 플래그 설정 (실제 이동·선택 동작은 Qt가 처리)
        - serialize()/deserialize() 기본 골격 (position, id, type)

    자식 클래스가 반드시 구현해야 하는 것 (QGraphicsItem 요구사항):
        - boundingRect() -> QRectF
        - paint(painter, option, widget) -> None

    사용 예:
        class TextBlock(BaseBlock):
            BLOCK_TYPE = "text"
            ...

        block = TextBlock(position=(100, 200))
        scene.addItem(block)
    """

    #: 저장 파일의 "type" 필드에 쓰일 문자열. 자식 클래스에서 반드시 덮어써야 한다.
    BLOCK_TYPE: str = "base"

    def __init__(self, position: tuple[float, float] = (0.0, 0.0), block_id: str | None = None) -> None:
        """
        Args:
            position: 씬 좌표계에서 블록이 놓일 (x, y)
            block_id: 블록 고유 id. 생략하면 자동 생성한다 (예: 파일에서 불러올 때는 지정해서 넘김).
        """
        super().__init__()

        self.block_id: str = block_id or f"blk_{uuid.uuid4().hex[:8]}"

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self._position_changed_since_press = False
        self._undo_snapshot_before_move: list[dict] | None = None
        self._locked = False

        self.setPos(*position)

    # --- 잠금 ---

    def is_locked(self) -> bool:
        """이 블록이 잠겨 있는지 (이동/크기조절/편집/삭제가 막혀 있는지)."""
        return self._locked

    def set_locked(self, locked: bool) -> None:
        """
        블록을 잠그거나 잠금을 해제한다.

        Note:
            이동은 ItemIsMovable 플래그 하나로 Qt가 알아서 막아준다(드래그
            이벤트 처리를 따로 가로챌 필요가 없음). 편집 진입/크기조절 손잡이/
            삭제는 각 블록·뷰가 is_locked()를 직접 확인해서 막는다. 선택
            (ItemIsSelectable)은 잠가도 그대로 둔다 — 잠금을 해제하려면
            먼저 선택할 수 있어야 하기 때문이다.
        """
        self._locked = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)
        self.update()

    def _selection_pen_color(self) -> QColor:
        """선택 테두리 색 — 잠긴 블록은 회색으로 구분해서 보여준다."""
        return _SELECTION_COLOR_LOCKED if self._locked else _SELECTION_COLOR

    def _draw_lock_badge(self, painter: QPainter, rect: QRectF) -> None:
        """잠긴 블록이면 우측 상단에 작은 자물쇠 표시를 그린다(선택 여부와 무관하게 항상)."""
        if not self._locked:
            return
        painter.save()
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(_LOCK_BADGE_COLOR)
        badge_rect = QRectF(rect.right() - _LOCK_BADGE_SIZE - 2, rect.top() + 2, _LOCK_BADGE_SIZE, _LOCK_BADGE_SIZE)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "\U0001f512")
        painter.restore()

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt 오버라이드 메서드는 camelCase 유지)
        """자식 클래스가 자신의 그려지는 영역 크기에 맞게 반드시 재정의해야 한다."""
        raise NotImplementedError("자식 블록 클래스는 boundingRect()를 구현해야 한다")

    def paint(
        self,
        painter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """자식 클래스가 자신의 실제 모습을 그리기 위해 반드시 재정의해야 한다."""
        raise NotImplementedError("자식 블록 클래스는 paint()를 구현해야 한다")

    def serialize(self) -> dict:
        """
        블록의 공통 속성을 dict로 직렬화한다.

        Returns:
            {"type", "id", "position"} 를 담은 dict.
            자식 클래스는 이 dict에 자신만의 필드(content, style 등)를 추가해서 반환한다.

        Note:
            file_io/file_manager.py(Phase 5)는 이 dict만 다루고, BaseBlock 객체 자체는
            알지 못한다 — 모듈 분리 원칙에 따라 file_io/ 패키지가 블록 클래스에 의존하지 않게 하기 위함.
            (참고: 애초에 이 패키지 이름을 "io"로 하지 않은 이유— Python 3.11+는 io 같은 표준
            라이브러리 모듈을 인터프리터에 frozen 상태로 미리 넣어둬서, 같은 이름의 로컬 패키지가
            무조건 가려진다. 실제로 Phase 5에서 이 문제가 터져서 file_io로 이름을 바꿨다.)
        """
        return {
            "type": self.BLOCK_TYPE,
            "id": self.block_id,
            "position": [self.pos().x(), self.pos().y()],
            "locked": self._locked,
        }

    def deserialize(self, data: dict) -> None:
        """
        dict로부터 블록의 공통 속성(위치)을 복원한다.

        Args:
            data: serialize()가 만든 것과 같은 구조의 dict

        Note:
            자식 클래스는 super().deserialize(data)를 먼저 호출한 뒤,
            자신만의 필드(content, style 등)를 이어서 복원해야 한다.
        """
        x, y = data["position"]
        self.setPos(x, y)
        self.set_locked(bool(data.get("locked", False)))

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        기본 동작은 아무것도 하지 않는다.

        더블클릭으로 편집 모드에 들어가야 하는 블록(TextBlock 등)은
        이 메서드를 재정의해서 자신만의 편집 진입 로직을 구현한다.
        """
        super().mouseDoubleClickEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):  # noqa: N802
        """위치가 실제로 바뀌면 표시해둔다 (mouseReleaseEvent에서 재계산 여부를 판단할 때 씀)."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._position_changed_since_press = True
        return super().itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """
        드래그 시작 시점을 표시해서, 이번 드래그로 실제 위치가 바뀌었는지 추적을 시작한다.

        동시에 지금 상태를 실행취소용으로 미리 캡처해둔다. 실제로 옮겨졌는지는
        떼는 순간에야 알 수 있으므로, 캡처만 해두고 기록(commit)은
        mouseReleaseEvent에서 한다 — 그냥 클릭(드래그 없음)이면 이 캡처는 버려진다.
        """
        self._position_changed_since_press = False
        scene = self.scene()
        self._undo_snapshot_before_move = (
            scene.capture_undo_snapshot() if scene is not None and hasattr(scene, "capture_undo_snapshot") else None
        )
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """
        드래그가 끝났을 때, 실제로 위치가 바뀌었다면 실행취소를 기록하고 문서 전체를 다시 계산한다.

        Note:
            블록은 화면상 위치(위→아래, 왼→오른) 순서로 계산되므로(계획서 5.1),
            드래그로 블록 순서 자체가 바뀔 수 있다. 수식 내용은 그대로여도
            "어떤 변수를 먼저/나중에 정의했는지"가 바뀌면 결과가 달라져야 하는데,
            지금까지는 텍스트를 편집(finish_editing)하거나 블록을 삭제할 때만
            재계산했고 "그냥 옮기기"는 빠져 있었다 — 그 buggy 케이스를 여기서 메운다.
            매 픽셀(mouseMoveEvent)마다가 아니라 마우스를 뗄 때 한 번만 하므로
            드래그 도중 버벅이지 않는다.
        """
        super().mouseReleaseEvent(event)
        if not self._position_changed_since_press:
            self._undo_snapshot_before_move = None
            return
        self._position_changed_since_press = False
        scene = self.scene()
        if scene is not None:
            if self._undo_snapshot_before_move is not None and hasattr(scene, "commit_undo_snapshot"):
                scene.commit_undo_snapshot(self._undo_snapshot_before_move)
            if hasattr(scene, "recalculate_all"):
                scene.recalculate_all()
        self._undo_snapshot_before_move = None
