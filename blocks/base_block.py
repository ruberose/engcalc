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

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)


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

        self.setPos(*position)

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
            io/file_manager.py(Phase 5)는 이 dict만 다루고, BaseBlock 객체 자체는
            알지 못한다 — 모듈 분리 원칙에 따라 io/ 패키지가 블록 클래스에 의존하지 않게 하기 위함.
        """
        return {
            "type": self.BLOCK_TYPE,
            "id": self.block_id,
            "position": [self.pos().x(), self.pos().y()],
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

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        기본 동작은 아무것도 하지 않는다.

        더블클릭으로 편집 모드에 들어가야 하는 블록(TextBlock 등)은
        이 메서드를 재정의해서 자신만의 편집 진입 로직을 구현한다.
        """
        super().mouseDoubleClickEvent(event)
