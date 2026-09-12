"""file_io/image_exporter.py 단위 테스트."""

import os
import tempfile

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene
from file_io.image_exporter import DEFAULT_MARGIN_PX, DEFAULT_SCALE, export_to_png

_app = QApplication.instance() or QApplication([])


def test_export_creates_valid_png_file():
    """블록이 있는 문서를 내보내면 진짜 PNG 파일이 생겨야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(10, 10))
    block.set_text("1. 설계조건")
    scene.addItem(block)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "output.png")
        result = export_to_png(scene, file_path)

        assert result is True
        assert os.path.exists(file_path)
        assert os.path.getsize(file_path) > 0

        image = QImage(file_path)
        assert not image.isNull()


def test_export_empty_scene_returns_false():
    """블록이 하나도 없는 빈 캔버스는 내보낼 게 없으므로 False를 돌려주고 파일을 만들지 않는다."""
    scene = DocumentScene()

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "empty.png")
        result = export_to_png(scene, file_path)

        assert result is False
        assert not os.path.exists(file_path)


def test_exported_image_size_matches_content_plus_margin_and_scale():
    """이미지 크기는 (내용 크기 + 여백*2) * 배율과 같아야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(0, 0))
    block.set_text("A")
    scene.addItem(block)
    content_rect = scene.itemsBoundingRect()

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "sized.png")
        export_to_png(scene, file_path, scale=1.0, margin_px=0.0)

        image = QImage(file_path)
        assert image.width() == round(content_rect.width())
        assert image.height() == round(content_rect.height())


def test_scale_doubles_pixel_dimensions():
    scene = DocumentScene()
    block = TextBlock(position=(0, 0))
    block.set_text("A")
    scene.addItem(block)

    with tempfile.TemporaryDirectory() as tmp_dir:
        path_1x = os.path.join(tmp_dir, "1x.png")
        path_2x = os.path.join(tmp_dir, "2x.png")
        export_to_png(scene, path_1x, scale=1.0, margin_px=0.0)
        export_to_png(scene, path_2x, scale=2.0, margin_px=0.0)

        image_1x = QImage(path_1x)
        image_2x = QImage(path_2x)
        assert image_2x.width() == image_1x.width() * 2
        assert image_2x.height() == image_1x.height() * 2


def test_default_scale_and_margin_are_used_when_not_specified():
    """기본값(2배 확대, 20px 여백)이 실제로 적용돼야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(0, 0))
    block.set_text("A")
    scene.addItem(block)
    content_rect = scene.itemsBoundingRect()

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "default.png")
        export_to_png(scene, file_path)

        image = QImage(file_path)
        expected_width = round((content_rect.width() + DEFAULT_MARGIN_PX * 2) * DEFAULT_SCALE)
        expected_height = round((content_rect.height() + DEFAULT_MARGIN_PX * 2) * DEFAULT_SCALE)
        assert image.width() == expected_width
        assert image.height() == expected_height


def test_background_is_white_not_transparent():
    """보고서 등에 붙여넣기 좋도록 배경이 투명이 아니라 흰색이어야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(0, 0))
    block.set_text("A")
    scene.addItem(block)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "bg.png")
        export_to_png(scene, file_path, margin_px=10.0)

        image = QImage(file_path)
        corner_pixel = image.pixelColor(0, 0)  # 내용에서 떨어진 여백 구석
        assert corner_pixel.red() == 255
        assert corner_pixel.green() == 255
        assert corner_pixel.blue() == 255
        assert corner_pixel.alpha() == 255  # 불투명


def test_export_respects_grid_visibility_toggle():
    """set_grid_visible(False)로 꺼둔 상태에서 내보내도 다시 True로 잘 복구될 수 있어야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(10, 10))
    block.set_text("hello")
    scene.addItem(block)

    scene.set_grid_visible(False)
    assert scene._grid_visible is False

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "output.png")
        export_to_png(scene, file_path)

    scene.set_grid_visible(True)
    assert scene._grid_visible is True
