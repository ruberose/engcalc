"""
canvas/document_scene.py의 문서 형식(자유 캔버스 / 용지 기반) 테스트.

사용자 요청: "무한 화이트보드 형태 외에 한글 프로그램처럼 A4 용지 기준의
문서 형식도 추가 선택지로 만들어달라"는 것 — 문서 형식은 새 문서를 만들 때
정해지고(ui/new_document_dialog.py), 이후 이 씬(DocumentScene)이 그 형식에
맞춰 배경(자유 캔버스 격자 vs 용지 여러 장)을 그린다.
"""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from blocks.math_block import MathBlock
from canvas.document_scene import SCENE_HEIGHT, SCENE_WIDTH, DocumentScene

_app = QApplication.instance() or QApplication([])


def _render_background(scene: DocumentScene, size: int = 300) -> None:
    """drawBackground()가 예외 없이 그려지는지 확인한다(픽셀 값까지는 검증하지 않음)."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    scene.render(painter, QRectF(0, 0, size, size), QRectF(0, 0, size, size))
    painter.end()


def test_default_format_is_freeform_with_original_scene_size():
    scene = DocumentScene()
    assert scene.document_format() == "freeform"
    assert scene.paper_size() == "A4"
    assert scene.sceneRect() == QRectF(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
    _render_background(scene)


def test_paper_format_starts_with_a_single_page():
    scene = DocumentScene()
    scene.set_document_format("paper", "A4")
    assert scene.document_format() == "paper"
    assert scene._page_count == 1
    _render_background(scene)


def test_unknown_document_format_falls_back_to_freeform():
    scene = DocumentScene()
    scene.set_document_format("paper", "A4")
    scene.set_document_format("이상한값")
    assert scene.document_format() == "freeform"


def test_unknown_paper_size_falls_back_to_a4():
    scene = DocumentScene()
    scene.set_document_format("paper", "존재하지않는용지")
    assert scene.paper_size() == "A4"


def test_page_count_grows_once_content_passes_first_page():
    scene = DocumentScene()
    scene.set_document_format("paper", "A4")

    _, page_h = scene._page_size_px()
    block = MathBlock(position=(10, page_h * 2))
    block.set_input_text("a = 1")
    scene.addItem(block)
    scene._sync_pages()  # 실제로는 scene.changed(비동기) 신호로 불림 — 여기선 바로 확인하려고 직접 호출

    assert scene._page_count > 1
    _render_background(scene)


def test_changed_signal_grows_pages_without_manual_call():
    """scene.changed 신호 연결 자체가 실제로 페이지를 늘리는지(이벤트 루프까지 포함해) 확인."""
    scene = DocumentScene()
    scene.set_document_format("paper", "A4")

    _, page_h = scene._page_size_px()
    block = MathBlock(position=(10, page_h * 2))
    block.set_input_text("a = 1")
    scene.addItem(block)
    _app.processEvents()

    assert scene._page_count > 1


def test_switching_back_to_freeform_restores_original_scene_size():
    scene = DocumentScene()
    scene.set_document_format("paper", "A4")
    scene.set_document_format("freeform")
    assert scene.sceneRect() == QRectF(0, 0, SCENE_WIDTH, SCENE_HEIGHT)


def test_paper_background_renders_when_grid_hidden_for_export():
    """PDF 내보내기 중(set_grid_visible(False))에는 예외 없이 흰 배경만 그려져야 한다."""
    scene = DocumentScene()
    scene.set_document_format("paper", "A4")
    scene.set_grid_visible(False)
    _render_background(scene)
    scene.set_grid_visible(True)
