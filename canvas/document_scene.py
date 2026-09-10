"""
문서 캔버스의 핵심 — QGraphicsScene 서브클래스.

배경 격자를 그리고, 빈 캔버스를 더블클릭했을 때 새 텍스트 블록을 만든다.
블록의 실제 로직(그리기, 편집)은 각 블록 클래스가 담당하고,
이 씬은 "격자 배경 + 블록 생성" 이라는 캔버스 차원의 책임만 진다.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QPainter, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

from blocks.base_block import BaseBlock
from blocks.image_block import ImageBlock, load_pixmap_from_file
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from canvas.grid import BACKGROUND_COLOR, draw_grid
from engine.scope import Scope

#: 새 문서 캔버스의 크기(px). 무한 캔버스는 아니지만 실무 계산서 하나 담기엔 충분히 크다.
SCENE_WIDTH = 4000
SCENE_HEIGHT = 4000

#: 저장 파일의 "type" 문자열 -> 블록 클래스. load_blocks_list()가 블록을 복원할 때 사용한다.
_BLOCK_CLASSES: dict[str, type[BaseBlock]] = {
    TextBlock.BLOCK_TYPE: TextBlock,
    MathBlock.BLOCK_TYPE: MathBlock,
    ImageBlock.BLOCK_TYPE: ImageBlock,
}


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
        self._grid_visible = True

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        """배경을 그린다. 평소엔 격자까지, PDF 내보내기 중엔 흰 배경만(격자는 인쇄 안 함)."""
        if self._grid_visible:
            draw_grid(painter, rect)
        else:
            painter.fillRect(rect, QBrush(BACKGROUND_COLOR))

    def set_grid_visible(self, visible: bool) -> None:
        """
        격자 배경을 켜고 끈다.

        Note:
            PDF 내보내기(file_io/pdf_exporter.py)는 이 씬을 그대로 QPainter에
            렌더링하는 방식을 쓰는데, 화면용 격자선까지 인쇄되면 지저분해 보이므로
            내보내는 동안만 잠깐 꺼둔다.
        """
        self._grid_visible = visible
        self.update()

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

    def create_image_block_from_file(self, scene_pos: QPointF, file_path: str) -> ImageBlock | None:
        """
        이미지 파일을 읽어 주어진 씬 좌표에 ImageBlock을 만들어 추가한다.

        메뉴("파일 > 이미지 삽입")와 드래그앤드롭(DocumentView) 양쪽에서 공용으로 쓴다.

        Returns:
            성공하면 만들어진 ImageBlock, 파일을 읽을 수 없으면 None
            (예: 손상된 파일, 지원하지 않는 형식) — 이 경우 블록을 만들지 않는다.
        """
        pixmap = load_pixmap_from_file(file_path)
        if pixmap.isNull():
            return None

        block = ImageBlock(position=(scene_pos.x(), scene_pos.y()), pixmap=pixmap)
        self.addItem(block)
        return block

    def to_blocks_list(self) -> list[dict]:
        """
        캔버스 위 모든 블록을 저장용 dict 리스트로 만든다.

        Note:
            문서 전체 메타데이터(제목, 작성자, 버전 등)는 이 씬이 알 필요가 없는
            "파일" 개념이므로 다루지 않는다 — app/main_window.py가 이 리스트를
            받아 {"version", "metadata", "blocks"} 구조로 감싼다.
        """
        return [item.serialize() for item in self.items() if isinstance(item, BaseBlock)]

    def load_blocks_list(self, blocks: list[dict]) -> None:
        """
        블록 dict 리스트로 캔버스를 새로 채운다.

        Args:
            blocks: to_blocks_list()가 만든 것과 같은 구조의 리스트

        Note:
            기존에 캔버스에 있던 블록은 모두 지운다("새로 만들기"/"파일 열기" 공용).
            알 수 없는 "type"(예: 이후 버전에서 추가된 블록을 예전 버전이 여는 경우)은
            조용히 건너뛴다 — 앱을 죽이는 대신 나머지 블록만이라도 복원하기 위함.
        """
        self.clear()
        for block_data in blocks:
            block_class = _BLOCK_CLASSES.get(block_data.get("type"))
            if block_class is None:
                continue
            block = block_class(block_id=block_data.get("id"))
            block.deserialize(block_data)
            self.addItem(block)
        self.recalculate_all()

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
