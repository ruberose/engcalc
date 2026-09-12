"""
문서 캔버스의 핵심 — QGraphicsScene 서브클래스.

배경 격자를 그리고, 빈 캔버스를 더블클릭했을 때 새 텍스트 블록을 만든다.
블록의 실제 로직(그리기, 편집)은 각 블록 클래스가 담당하고,
이 씬은 "격자 배경 + 블록 생성" 이라는 캔버스 차원의 책임만 진다.
"""

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap, QTransform
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

#: 실행취소 스택에 담아둘 최대 단계 수. 너무 많이 쌓이면 메모리만 차지하므로 제한한다.
MAX_UNDO_STEPS = 50

#: 붙여넣은 블록을 원본과 겹치지 않게 어긋나게 놓는 거리(px).
_PASTE_OFFSET = 20.0

#: align_selected_blocks()가 받는 유효한 정렬 기준 값.
_ALIGN_MODES = frozenset({"left", "right", "top", "bottom", "center_h", "center_v"})

#: "용지 기반" 문서 형식에서 고를 수 있는 용지 크기(mm). 나중에 다른 용지를
#: 추가할 땐 이 딕셔너리에 항목만 더하면 된다(다른 코드는 안 바꿔도 됨).
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {"A4": (210.0, 297.0)}

#: 화면에 용지를 그릴 때 쓰는 가상 해상도(dpi). file_io/pdf_exporter.py의
#: RESOLUTION_DPI와 같은 값이지만, 저 쪽은 실제 PDF 출력용이라 여긴 화면
#: 표시 전용으로 따로 둔다(둘을 같은 모듈에 묶어야 할 이유가 없어서 분리 유지).
_SCREEN_DPI = 96

#: 용지들 사이(및 첫 용지 위/스크롤 여백)의 회색 "책상" 간격(px).
_PAGE_GAP_PX = 40.0

_PAGE_DESK_COLOR = QColor(178, 178, 178)
_PAGE_BORDER_COLOR = QColor(140, 140, 140)
_PAGE_NUMBER_COLOR = QColor(110, 110, 110)


def _mm_to_px(value_mm: float, dpi: float = _SCREEN_DPI) -> float:
    """mm 단위를 화면 표시용 픽셀로 변환한다 (1인치 = 25.4mm)."""
    return value_mm / 25.4 * dpi

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

    #: recalculate_all()이 끝나서 변수 목록이 새로 갱신될 때마다 울린다.
    #: ui/variable_inspector.py가 이 신호를 구독해서 목록을 다시 그린다.
    variables_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self._grid_visible = True
        self._scope = Scope()
        self._variable_blocks: dict[str, MathBlock] = {}

        # --- 문서 형식 ("freeform": 기존 자유 캔버스, "paper": A4 등 용지 기반) ---
        self._document_format: str = "freeform"
        self._paper_size: str = "A4"
        self._page_count: int = 1

        # --- 실행취소 / 다시실행 / 클립보드 ---
        # 문서 전체를 to_blocks_list()로 스냅샷 떠서 스택에 쌓는 방식이다.
        # 블록별로 "무슨 동작이었는지"를 따로 기록하는 대신, 파일 저장/불러오기에
        # 이미 쓰는 (검증된) 직렬화 골격을 그대로 재사용해서 단순하게 구현했다.
        self._undo_stack: list[list[dict]] = []
        self._redo_stack: list[list[dict]] = []
        self._clipboard: list[dict] = []

        # 용지 모드에서 블록이 늘어나 페이지가 모자라지면 자동으로 페이지를
        # 늘린다 — changed는 블록 추가/삭제/이동/불러오기 등 내용이 바뀌는
        # 모든 경로에서 공통으로 울리므로, 그 경로들 각각에 훅을 심는 대신
        # 여기 한 곳에서만 처리한다(자유 캔버스면 아무 일도 안 하고 바로 리턴).
        self.changed.connect(self._sync_pages)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        """배경을 그린다. 평소엔 격자(또는 용지)까지, PDF 내보내기 중엔 흰 배경만(격자는 인쇄 안 함)."""
        if not self._grid_visible:
            painter.fillRect(rect, QBrush(BACKGROUND_COLOR))
            return
        if self._document_format == "paper":
            self._draw_paper_background(painter, rect)
        else:
            draw_grid(painter, rect)

    def _draw_paper_background(self, painter: QPainter, rect: QRectF) -> None:
        """용지 기반 문서의 배경: 회색 "책상" 바탕 위에 페이지마다 흰 용지 + 격자 + 쪽 번호."""
        painter.fillRect(rect, QBrush(_PAGE_DESK_COLOR))
        pages = self._page_rects()
        for index, page_rect in enumerate(pages):
            visible = page_rect.intersected(rect)
            if visible.isEmpty():
                continue
            draw_grid(painter, visible)
            pen = QPen(_PAGE_BORDER_COLOR)
            pen.setWidth(0)  # 코스메틱 펜: 확대/축소와 무관하게 항상 1px
            painter.setPen(pen)
            painter.drawRect(page_rect)
            self._draw_page_number(painter, page_rect, index + 1, len(pages))

    def _draw_page_number(self, painter: QPainter, page_rect: QRectF, page_number: int, total_pages: int) -> None:
        """용지 아래 여백에 작게 "N / 전체" 쪽 번호를 적는다."""
        painter.save()
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QPen(_PAGE_NUMBER_COLOR))
        label_rect = QRectF(page_rect.left(), page_rect.bottom() + 4, page_rect.width(), _PAGE_GAP_PX - 8)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"{page_number} / {total_pages}")
        painter.restore()

    def set_grid_visible(self, visible: bool) -> None:
        """
        격자 배경을 켜고 끈다.

        Note:
            PDF 내보내기(file_io/pdf_exporter.py)는 이 씬을 그대로 QPainter에
            렌더링하는 방식을 쓰는데, 화면용 격자선(용지 모드라면 회색 배경/쪽
            경계/쪽 번호까지)이 인쇄되면 지저분해 보이므로 내보내는 동안만
            잠깐 꺼둔다 — 꺼져 있으면 문서 형식과 무관하게 흰 배경만 그려진다.
        """
        self._grid_visible = visible
        self.update()

    def is_grid_visible(self) -> bool:
        """격자 배경이 지금 켜져 있는지. 내보내기 전후로 사용자의 원래 설정을 복원할 때 쓴다."""
        return self._grid_visible

    # --- 문서 형식 (자유 캔버스 / 용지 기반) ---

    def set_document_format(self, document_format: str, paper_size: str = "A4") -> None:
        """
        문서 형식을 정한다.

        Args:
            document_format: "freeform"(자유 캔버스) 또는 "paper"(용지 기반). 그 외
                알 수 없는 값은 "freeform"으로 취급한다(옛 파일 호환).
            paper_size: document_format이 "paper"일 때 쓸 용지 이름(PAPER_SIZES_MM의 키).
                모르는 이름이면 "A4"로 대체한다.

        Note:
            새 문서를 만들 때, 또는 파일을 열 때 한 번만 부르는 걸 전제로 한다 —
            기존 문서를 열어둔 채로 형식만 바꾸는 UI는 이번 범위에 없다.
        """
        self._document_format = document_format if document_format == "paper" else "freeform"
        self._paper_size = paper_size if paper_size in PAPER_SIZES_MM else "A4"
        if self._document_format == "paper":
            self._page_count = 1
            self._update_scene_rect_for_pages()
            self._sync_pages()  # 이미 내용이 있는 문서를 열 때는 그 내용만큼 페이지 수를 바로 맞춘다
        else:
            self.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self.update()

    def document_format(self) -> str:
        """현재 문서 형식("freeform" 또는 "paper"). 저장할 때 메타데이터에 담긴다."""
        return self._document_format

    def paper_size(self) -> str:
        """현재 용지 이름. document_format()이 "paper"일 때만 의미가 있다."""
        return self._paper_size

    def _page_size_px(self) -> tuple[float, float]:
        """현재 paper_size의 (너비, 높이)를 화면 픽셀 단위로 반환한다."""
        mm_w, mm_h = PAPER_SIZES_MM.get(self._paper_size, PAPER_SIZES_MM["A4"])
        return _mm_to_px(mm_w), _mm_to_px(mm_h)

    def _page_rects(self) -> list[QRectF]:
        """현재 페이지 수만큼, 세로로 쌓인 용지 사각형 목록(위→아래 순서)."""
        page_w, page_h = self._page_size_px()
        rects = []
        for index in range(self._page_count):
            top = _PAGE_GAP_PX + index * (page_h + _PAGE_GAP_PX)
            rects.append(QRectF(_PAGE_GAP_PX, top, page_w, page_h))
        return rects

    def _update_scene_rect_for_pages(self) -> None:
        """현재 _page_count에 맞춰 씬 사각형(스크롤 범위)을 다시 계산한다."""
        page_w, page_h = self._page_size_px()
        width = page_w + 2 * _PAGE_GAP_PX
        height = _PAGE_GAP_PX + self._page_count * (page_h + _PAGE_GAP_PX)
        self.setSceneRect(0, 0, width, height)

    def _sync_pages(self, _regions: list[QRectF] | None = None) -> None:
        """
        내용이 바뀔 때마다(self.changed 신호) 불려서, 필요한 페이지 수를 맞춘다.

        용지 기반 문서에서 내용이 마지막 페이지 아래로 넘어가면 페이지를 자동으로
        늘린다(워드처럼) — 항상 맨 아래에 빈 페이지 하나가 남도록 여유를 둔다.
        자유 캔버스 문서면 아무 일도 하지 않는다.
        """
        if self._document_format != "paper":
            return
        _, page_h = self._page_size_px()
        content_rect = self.itemsBoundingRect()
        if content_rect.isEmpty():
            page_count = 1  # 내용이 없는 새 문서는 빈 페이지 1장으로 시작한다
        else:
            band = page_h + _PAGE_GAP_PX
            used_height = max(content_rect.bottom() - _PAGE_GAP_PX, 0.0)
            pages_for_content = max(1, math.ceil(used_height / band))
            page_count = pages_for_content + 1  # 마지막 페이지 아래에 빈 페이지 한 장을 여유로 남긴다
        if page_count == self._page_count:
            return
        self._page_count = page_count
        self._update_scene_rect_for_pages()

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
        """
        주어진 씬 좌표에 새 TextBlock을 만들어 캔버스에 추가한다.

        Note:
            생성 직전 상태를 캡처해서 편집기에 넘겨준다 — 만들자마자 바로 타이핑을
            시작하는 게 이 앱의 관례라, "생성"과 "그 안에 처음 타이핑"을 실행취소
            한 단계로 묶기 위함이다(따로 기록하면 Ctrl+Z 두 번 눌러야 빈 블록까지
            깔끔히 사라진다). finish_editing()에서 실제로 뭔가 달라졌을 때만 이
            스냅샷이 커밋된다.
        """
        before = self.capture_undo_snapshot()
        block = TextBlock(position=(scene_pos.x(), scene_pos.y()))
        self.addItem(block)
        block.start_editing(undo_snapshot=before)  # 만들자마자 바로 타이핑할 수 있게 편집 모드로 시작
        return block

    def _create_math_block(self, scene_pos: QPointF) -> MathBlock:
        """주어진 씬 좌표에 새 MathBlock을 만들어 캔버스에 추가한다 (실행취소 처리는 _create_text_block 참고)."""
        before = self.capture_undo_snapshot()
        block = MathBlock(position=(scene_pos.x(), scene_pos.y()))
        self.addItem(block)
        block.start_editing(undo_snapshot=before)
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
        return self.create_image_block_from_pixmap(scene_pos, pixmap)

    def create_image_block_from_pixmap(self, scene_pos: QPointF, pixmap: QPixmap, caption: str = "") -> ImageBlock | None:
        """
        이미 메모리에 있는 QPixmap으로 주어진 씬 좌표에 ImageBlock을 만들어 추가한다.

        메뉴/드래그앤드롭용 create_image_block_from_file()과, 클립보드 이미지
        붙여넣기(app/main_window.py의 _on_paste)가 공용으로 쓴다 — 파일이든
        클립보드든 결국 QPixmap 하나로 귀결되므로, 실제 블록 생성 로직은
        여기 한 곳에만 있다.

        Returns:
            성공하면 만들어진 ImageBlock, pixmap이 비어 있으면(null) None.
        """
        if pixmap.isNull():
            return None

        before = self.capture_undo_snapshot()
        block = ImageBlock(position=(scene_pos.x(), scene_pos.y()), pixmap=pixmap, caption=caption)
        self.addItem(block)
        self.commit_undo_snapshot(before)
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
            알 수 없는 "type"(예: 이후 버전에서 추가된 블록을 예전 버전이 여는 경우)이나
            필수 필드가 빠진 손상된 블록은 조용히 건너뛴다 — 블록 하나가 깨졌다고
            문서 전체를 못 열게 되는 것보다, 나머지 블록만이라도 복원하는 게 낫다.
        """
        self.clear()
        for block_data in blocks:
            block_class = _BLOCK_CLASSES.get(block_data.get("type"))
            if block_class is None:
                continue
            try:
                block = block_class(block_id=block_data.get("id"))
                block.deserialize(block_data)
            except (KeyError, ValueError, TypeError):
                continue  # position 등 필수 필드 누락/형식 오류 - 이 블록만 건너뜀
            self.addItem(block)
        self.recalculate_all()

    # --- 실행취소 / 다시실행 ---

    def capture_undo_snapshot(self) -> list[dict]:
        """
        지금 상태를 스냅샷으로 캡처한다 (아직 실행취소 스택에 넣지는 않음).

        Note:
            드래그·리사이즈처럼 "실제로 뭔가 바뀔 수도, 안 바뀔 수도 있는" 동작은
            시작 시점에 이 메서드로 미리 캡처해두고, 끝난 뒤 commit_undo_snapshot()에
            넘겨서 확정한다 (동작이 끝나봐야 "진짜 바뀌었는지" 알 수 있으므로).
        """
        return self.to_blocks_list()

    def commit_undo_snapshot(self, before: list[dict]) -> None:
        """
        capture_undo_snapshot()으로 받아둔 '이전' 상태를 실행취소 스택에 확정 기록한다.

        Args:
            before: 변경 시작 전에 capture_undo_snapshot()으로 캡처해둔 스냅샷.

        Note:
            지금 상태와 비교해서 실제로 달라진 경우에만 기록한다 — 그래야 클릭만
            하고 아무것도 안 바꿨거나, 손잡이를 눌렀다 그대로 뗀 경우처럼 "아무 일도
            안 일어난" 동작이 실행취소 기록을 쓸데없이 채우지 않는다.
        """
        if before == self.to_blocks_list():
            return
        self._undo_stack.append(before)
        del self._redo_stack[:]
        if len(self._undo_stack) > MAX_UNDO_STEPS:
            del self._undo_stack[0]

    def can_undo(self) -> bool:
        """실행취소할 게 남아있는지."""
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        """다시실행할 게 남아있는지."""
        return bool(self._redo_stack)

    def undo(self) -> None:
        """바로 전 실행취소 단계로 되돌린다. 되돌릴 게 없으면 아무 일도 하지 않는다."""
        if not self._undo_stack:
            return
        self._redo_stack.append(self.to_blocks_list())
        previous = self._undo_stack.pop()
        self.clearSelection()
        self.load_blocks_list(previous)

    def redo(self) -> None:
        """실행취소를 한 단계 되돌린다(다시실행). 되돌릴 게 없으면 아무 일도 하지 않는다."""
        if not self._redo_stack:
            return
        self._undo_stack.append(self.to_blocks_list())
        following = self._redo_stack.pop()
        self.clearSelection()
        self.load_blocks_list(following)

    # --- 선택 ---

    def select_all_blocks(self) -> None:
        """캔버스 위 모든 블록을 선택 상태로 만든다."""
        for item in self.items():
            if isinstance(item, BaseBlock):
                item.setSelected(True)

    # --- 잠금 ---

    def set_locked_for_selected(self, locked: bool) -> None:
        """선택된 블록(들)을 모두 잠그거나 잠금을 해제한다. 실행취소 가능."""
        blocks = [item for item in self.selectedItems() if isinstance(item, BaseBlock)]
        if not blocks:
            return

        before = self.capture_undo_snapshot()
        for block in blocks:
            block.set_locked(locked)
        self.commit_undo_snapshot(before)

    # --- 복사 / 붙여넣기 / 복제 ---

    def copy_selected_blocks(self) -> None:
        """선택된 블록들을 이 씬 안에서만 쓰는 내부 클립보드에 담는다."""
        self._clipboard = [item.serialize() for item in self.selectedItems() if isinstance(item, BaseBlock)]

    def can_paste(self) -> bool:
        """붙여넣을 내용이 클립보드에 있는지."""
        return bool(self._clipboard)

    def paste_blocks(self) -> list[BaseBlock]:
        """
        클립보드에 담긴 블록들을 원본에서 약간 어긋난 위치에 새로 만들어 추가한다.

        Note:
            붙여넣은 블록들만 선택 상태로 남겨서, 바로 이어서 옮기거나 지우기
            편하게 한다. 실제 복제 작업은 duplicate_selected_blocks()와
            _clone_blocks_from_data()를 공유한다 — 소스가 클립보드냐 지금
            선택된 블록이냐만 다르다.
        """
        if not self._clipboard:
            return []

        before = self.capture_undo_snapshot()
        self.clearSelection()
        pasted = self._clone_blocks_from_data(self._clipboard)

        if pasted:
            self.commit_undo_snapshot(before)
            self.recalculate_all()
        return pasted

    def duplicate_selected_blocks(self) -> list[BaseBlock]:
        """
        지금 선택된 블록(들)을 원본에서 약간 어긋난 위치에 바로 복제한다(Ctrl+D).

        Note:
            복사(Ctrl+C) + 붙여넣기(Ctrl+V)와 결과는 같지만 클립보드를 거치지
            않는다 — 이전에 복사해둔 내용이 있다면 복제 후에도 그대로
            붙여넣을 수 있어야 하기 때문이다(클립보드를 건드리면 안 됨).
        """
        selected_data = [item.serialize() for item in self.selectedItems() if isinstance(item, BaseBlock)]
        if not selected_data:
            return []

        before = self.capture_undo_snapshot()
        self.clearSelection()
        duplicated = self._clone_blocks_from_data(selected_data)

        if duplicated:
            self.commit_undo_snapshot(before)
            self.recalculate_all()
        return duplicated

    def _clone_blocks_from_data(self, blocks_data: list[dict]) -> list[BaseBlock]:
        """
        block dict 목록으로부터 새 블록들을 만들어 원본에서 살짝 어긋난 위치에
        추가하고 선택 상태로 만든다. paste_blocks()/duplicate_selected_blocks() 공용.

        Note:
            새 블록은 각자 새로운 id를 받는다(생성자에 block_id를 넘기지 않으므로
            자동 생성됨) — 원본과 id가 겹치면 안 되기 때문이다.
        """
        cloned: list[BaseBlock] = []
        for block_data in blocks_data:
            block_class = _BLOCK_CLASSES.get(block_data.get("type"))
            if block_class is None:
                continue
            block = block_class()
            try:
                block.deserialize(block_data)
            except (KeyError, ValueError, TypeError):
                continue
            block.setPos(block.pos().x() + _PASTE_OFFSET, block.pos().y() + _PASTE_OFFSET)
            self.addItem(block)
            block.setSelected(True)
            cloned.append(block)
        return cloned

    # --- 정렬 ---

    def align_selected_blocks(self, mode: str) -> None:
        """
        선택된 블록 2개 이상을 한 기준선에 맞춰 정렬한다.

        Args:
            mode: "left"/"right"/"top"/"bottom"(가장자리 맞춤) 또는
                "center_h"/"center_v"(가운데/중간 맞춤). 그 외 값이거나
                선택된 블록이 2개 미만이면 아무 것도 하지 않는다.

        Note:
            기준은 항상 "선택된 블록들 전체를 감싸는 사각형"이다 — 예를 들어
            "left"는 그 사각형의 가장 왼쪽 x좌표에 모든 블록의 왼쪽 변을
            맞춘다. 어느 한 블록을 따로 "기준"으로 고르게 하지 않는 쪽이
            (디자인 툴에서 흔한 관례이기도 하고) 훨씬 단순하다. 정렬로 블록의
            위아래 순서가 바뀔 수 있으므로("계산 순서" 규칙) 끝나면 다시
            계산한다.
        """
        blocks = [item for item in self.selectedItems() if isinstance(item, BaseBlock) and not item.is_locked()]
        if len(blocks) < 2 or mode not in _ALIGN_MODES:
            return

        geometry = {block: (block.pos(), block.boundingRect()) for block in blocks}
        lefts = [pos.x() for pos, _rect in geometry.values()]
        rights = [pos.x() + rect.width() for pos, rect in geometry.values()]
        tops = [pos.y() for pos, _rect in geometry.values()]
        bottoms = [pos.y() + rect.height() for pos, rect in geometry.values()]

        before = self.capture_undo_snapshot()
        if mode == "left":
            target = min(lefts)
            for block, (pos, _rect) in geometry.items():
                block.setPos(target, pos.y())
        elif mode == "right":
            target = max(rights)
            for block, (pos, rect) in geometry.items():
                block.setPos(target - rect.width(), pos.y())
        elif mode == "center_h":
            target = (min(lefts) + max(rights)) / 2
            for block, (pos, rect) in geometry.items():
                block.setPos(target - rect.width() / 2, pos.y())
        elif mode == "top":
            target = min(tops)
            for block, (pos, _rect) in geometry.items():
                block.setPos(pos.x(), target)
        elif mode == "bottom":
            target = max(bottoms)
            for block, (pos, rect) in geometry.items():
                block.setPos(pos.x(), target - rect.height())
        elif mode == "center_v":
            target = (min(tops) + max(bottoms)) / 2
            for block, (pos, rect) in geometry.items():
                block.setPos(pos.x(), target - rect.height() / 2)

        self.commit_undo_snapshot(before)
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
        variable_blocks: dict[str, MathBlock] = {}

        math_blocks = [item for item in self.items() if isinstance(item, MathBlock)]
        math_blocks.sort(key=lambda block: (block.pos().y(), block.pos().x()))
        for block in math_blocks:
            block.evaluate(scope)
            result = block.result()
            if result is not None and not result.is_error and result.variable_name is not None:
                variable_blocks[result.variable_name] = block

        self._scope = scope
        self._variable_blocks = variable_blocks
        self.variables_changed.emit()

    def variables(self) -> dict[str, Any]:
        """
        가장 최근 recalculate_all() 기준으로, 현재 문서에 정의된 변수 이름 -> 값.

        ui/variable_inspector.py가 이걸로 변수 목록을 그린다.
        """
        return self._scope.as_dict()

    def block_for_variable(self, name: str) -> MathBlock | None:
        """주어진 이름의 변수를 정의한 MathBlock을 반환한다. 없으면 None."""
        return self._variable_blocks.get(name)

    # --- 찾기 ---

    def find_blocks(self, query: str) -> list[BaseBlock]:
        """
        검색어가 내용에 포함된 블록들을 화면 순서(위→아래, 왼→오른)로 찾는다.

        Args:
            query: 찾을 문자열. 대소문자는 구분하지 않는다. 빈 문자열이면 빈 리스트를 돌려준다.

        Note:
            수식 블록은 입력 원문(예: "F_y = 300"), 텍스트 블록은 내용, 이미지
            블록은 캡션을 검색 대상으로 삼는다 — 계산 결과값 자체는 검색하지
            않는다(결과는 입력에서 파생된 값이라, 입력을 찾는 게 더 직접적이다).
        """
        query = query.strip()
        if not query:
            return []
        query_lower = query.lower()
        matches = [
            item
            for item in self.items()
            if isinstance(item, BaseBlock) and query_lower in _searchable_text(item).lower()
        ]
        matches.sort(key=lambda block: (block.pos().y(), block.pos().x()))
        return matches


def _searchable_text(block: BaseBlock) -> str:
    """블록 종류별로 찾기 대상이 되는 텍스트를 뽑아낸다."""
    if isinstance(block, MathBlock):
        return block.input_text()
    if isinstance(block, TextBlock):
        return block.text()
    if isinstance(block, ImageBlock):
        return block.caption()
    return ""
