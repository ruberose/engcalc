"""
문서 캔버스의 핵심 — QGraphicsScene 서브클래스.

배경 격자를 그리고, 빈 캔버스를 더블클릭했을 때 새 텍스트 블록을 만든다.
블록의 실제 로직(그리기, 편집)은 각 블록 클래스가 담당하고,
이 씬은 "격자 배경 + 블록 생성" 이라는 캔버스 차원의 책임만 진다.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from canvas.grid import draw_grid
from engine.scope import Scope

#: 새 문서 캔버스의 크기(px). 무한 캔버스는 아니지만 실무 계산서 하나 담기엔 충분히 크다.
SCENE_WIDTH = 4000
SCENE_HEIGHT = 4000


class DocumentScene(QGraphicsScene):
    """
    EngCalc 문서 캔버스.

    사용 예:
        scene = DocumentScene()
        view = DocumentView(scene)
        # 캔버스 빈 곳을 더블클릭하면 그 자리에 수식 블록이 생긴다
        # (Ctrl+더블클릭이면 텍스트 블록)
    """

    def __init__(self) -> None:
        super().__init__()
        self.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        """배경 격자를 그린다 (실제 계산은 canvas/grid.py에 위임)."""
        draw_grid(painter, rect)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """
        빈 캔버스를 더블클릭하면 블록을 만든다.

        이 프로그램의 핵심 기능은 계산이므로, 그냥 더블클릭하면 수식 블록을 만든다.
        Ctrl을 누른 채 더블클릭하면 텍스트 블록(제목/설명용)을 만든다.
        (블록 종류를 고르는 툴바는 Phase 7에서 추가될 예정 — 그 전까지의 임시 단축키.)

        Note:
            더블클릭 위치에 이미 블록이 있으면(itemAt이 뭔가를 찾으면)
            새로 만들지 않고 기본 동작에 맡긴다 — 그래야 그 블록 자신의
            mouseDoubleClickEvent(예: TextBlock/MathBlock의 편집 모드 진입)가 정상 호출된다.
        """
        item = self.itemAt(event.scenePos(), QTransform())
        if item is not None:
            super().mouseDoubleClickEvent(event)
            return

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._create_text_block(event.scenePos())
        else:
            self._create_math_block(event.scenePos())
        event.accept()

    def _create_text_block(self, scene_pos: QPointF) -> TextBlock:
        """주어진 씬 좌표에 새 TextBlock을 만들어 캔버스에 추가한다."""
        block = TextBlock(position=(scene_pos.x(), scene_pos.y()))
        self.addItem(block)
        block.start_editing()  # 만들자마자 바로 타이핑할 수 있게 편집 모드로 시작
        return block

    def _create_math_block(self, scene_pos: QPointF) -> MathBlock:
        """주어진 씬 좌표에 새 MathBlock을 만들어 캔버스에 추가한다."""
        block = MathBlock(position=(scene_pos.x(), scene_pos.y()))
        self.addItem(block)
        block.start_editing()
        return block

    def recalculate_all(self) -> None:
        """
        문서 전체를 처음부터 다시 계산한다.

        블록을 화면상 위치(y좌표 우선, 같으면 x좌표) 순서로 정렬해서 하나씩
        evaluate()하며, 변수 대입은 Scope에 누적되어 다음 블록이 참조할 수 있다
        (계획서 5.1 계산 순서 규칙).

        Note:
            블록 하나가 바뀔 때마다 "그 이후 블록만" 다시 계산하는 게 더 효율적이지만,
            계획서 5.3에 따라 1차 목표에서는 정확성과 단순함을 우선해 전체를 다시 계산한다.
            블록이 많아져 성능 문제가 생기면 그때 부분 재계산으로 최적화한다.
        """
        scope = Scope()
        math_blocks = [item for item in self.items() if isinstance(item, MathBlock)]
        math_blocks.sort(key=lambda block: (block.pos().y(), block.pos().x()))
        for block in math_blocks:
            block.evaluate(scope)
