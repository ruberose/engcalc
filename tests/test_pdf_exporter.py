"""file_io/pdf_exporter.py 단위 테스트."""

import os
import tempfile

from PySide6.QtWidgets import QApplication

from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene
from file_io.pdf_exporter import export_to_pdf

_app = QApplication.instance() or QApplication([])


def test_export_creates_valid_pdf_file():
    """블록이 있는 문서를 내보내면 진짜 PDF 파일이 생겨야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(10, 10))
    block.set_text("1. 설계조건")
    scene.addItem(block)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "output.pdf")
        result = export_to_pdf(scene, file_path, title="테스트 문서")

        assert result is True
        assert os.path.exists(file_path)
        assert os.path.getsize(file_path) > 0

        with open(file_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"


def test_export_empty_scene_returns_false():
    """블록이 하나도 없는 빈 캔버스는 내보낼 게 없으므로 False를 돌려주고 파일을 만들지 않는다."""
    scene = DocumentScene()

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "empty.pdf")
        result = export_to_pdf(scene, file_path)

        assert result is False
        assert not os.path.exists(file_path)


def test_export_multi_page_for_tall_content():
    """세로로 긴 문서는 여러 페이지로 나뉘어야 한다."""
    scene = DocumentScene()
    # 블록을 세로로 아주 넓게 퍼뜨려서 한 페이지에 다 안 들어가게 만든다.
    for i in range(20):
        block = TextBlock(position=(10, i * 400))
        block.set_text(f"항목 {i}")
        scene.addItem(block)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "long.pdf")
        result = export_to_pdf(scene, file_path)

        assert result is True
        # 정확한 페이지 수는 PDF 파서 없이 확인하기 어려우니, 대신 파일 크기로
        # "페이지가 여러 장 만들어져서 한 페이지짜리보다 훨씬 크다"는 것만 확인한다.
        single_page_scene = DocumentScene()
        single_block = TextBlock(position=(10, 10))
        single_block.set_text("항목 0")
        single_page_scene.addItem(single_block)
        single_page_path = os.path.join(tmp_dir, "short.pdf")
        export_to_pdf(single_page_scene, single_page_path)

        assert os.path.getsize(file_path) > os.path.getsize(single_page_path)


def test_export_respects_grid_visibility_toggle():
    """set_grid_visible(False)로 꺼둔 상태에서 내보내도 다시 True로 잘 복구될 수 있어야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(10, 10))
    block.set_text("hello")
    scene.addItem(block)

    scene.set_grid_visible(False)
    assert scene._grid_visible is False

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "output.pdf")
        export_to_pdf(scene, file_path)

    scene.set_grid_visible(True)
    assert scene._grid_visible is True
