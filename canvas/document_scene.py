"""
문서 캔버스의 핵심 — QGraphicsScene 서브클래스.

배경 격자를 그리고, 빈 캔버스를 더블클릭했을 때 새 텍스트 블록을 만든다.
블록의 실제 로직(그리기, 편집)은 각 블록 클래스가 담당하고,
이 씬은 "격자 배경 + 블록 생성" 이라는 캔버스 차원의 책임만 진다.
"""

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

from blocks.text_block import TextBlock
from canvas.grid import draw_grid

#: 새 문서 캔버스의 크기(px). 무한 캔버스는 아니지만 실무 계산서 하나 담기엔 충분히 크다.
SCENE_WIDTH = 4000
SCENE_HEIGHT = 4000


class DocumentScene(QGraphicsScene):
    """
    EngCalc 문서 캔버스.

    사용 예:
        scene = DocumentScene()
        view = DocumentView(scene)
        # 캔버스 빈 곳을 더블클릭하면 그 자리에 텍스트 블록이 생긴다
    """

    def __init__(self) -> None:
        super().__init__()
        self.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        """배경 격자를 그린다 (실제 계산은 canvas/grid.py에 위임)."""
        draw_grid(painter, rect)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """
        빈 캔버스를 더블클릭하면 텍스트 블록을 만든다.

        Note:
            더블클릭 위치에 이미 블록이 있으면(itemAt이 뭔가를 찾으면)
            새로 만들지 않고 기본 동작에 맡긴다 — 그래야 그 블록 자신의
            mouseDoubleClickEvent(예: TextBlock의 편집 모드 진입)가 정상적으로 호출된다.
        """
        item = self.itemAt(event.scenePos(), QTransform())
        if item is None:
            self._create_text_block(event.scenePos())
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def _create_text_block(self, scene_pos: QPointF) -> TextBlock:
        """주어진 씬 좌표에 새 TextBlock을 만들어 캔버스에 추가한다."""
        block = TextBlock(position=(scene_pos.x(), scene_pos.y()))
        self.addItem(block)
        block.start_editing()  # 만들자마자 바로 타이핑할 수 있게 편집 모드로 시작
        return block
