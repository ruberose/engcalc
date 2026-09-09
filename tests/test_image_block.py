"""blocks/image_block.py 단위 테스트."""

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from blocks.image_block import ImageBlock, _pixmap_from_base64, _pixmap_to_base64

# QPixmap은 내부적으로 QGuiApplication이 있어야 동작한다 (테스트 프로세스 전체에서 하나만 필요).
_app = QApplication.instance() or QApplication([])


def _make_test_pixmap(width: int = 40, height: int = 20) -> QPixmap:
    """테스트용으로 단색 QPixmap을 하나 만든다 (실제 이미지 파일 없이 테스트하기 위함)."""
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(10, 20, 30))
    return pixmap


def test_pixmap_base64_round_trip():
    """QPixmap -> base64 -> QPixmap 왕복 변환 시 크기가 보존되어야 한다."""
    original = _make_test_pixmap(40, 20)
    encoded = _pixmap_to_base64(original)
    restored = _pixmap_from_base64(encoded)

    assert not restored.isNull()
    assert restored.width() == 40
    assert restored.height() == 20


def test_image_block_default_size_matches_pixmap():
    """픽스맵을 주고 만들면 블록 크기가 픽스맵 크기와 같아야 한다."""
    pixmap = _make_test_pixmap(80, 60)
    block = ImageBlock(position=(0, 0), pixmap=pixmap)

    rect = block.boundingRect()
    assert rect.width() == 80
    assert rect.height() == 60


def test_image_block_serialize_deserialize_round_trip():
    """직렬화 후 새 블록에 복원하면 위치/크기/이미지가 그대로 돌아와야 한다."""
    pixmap = _make_test_pixmap(50, 30)
    original = ImageBlock(position=(120, 200), pixmap=pixmap, caption="단면도")

    data = original.serialize()
    assert data["type"] == "image"
    assert data["position"] == [120.0, 200.0]
    assert data["size"] == [50.0, 30.0]
    assert data["caption"] == "단면도"
    assert data["image_data"]  # 비어있지 않은 base64 문자열

    restored = ImageBlock()
    restored.deserialize(data)

    assert restored.pos().toTuple() == (120.0, 200.0)
    assert restored.boundingRect().width() == 50
    assert restored.boundingRect().height() == 30
    assert restored._caption == "단면도"
    assert not restored._pixmap.isNull()


def test_image_block_without_pixmap_is_not_null_state():
    """이미지 없이 만들어도(플레이스홀더 상태) 크기가 유효해야 하고 죽지 않아야 한다."""
    block = ImageBlock(position=(0, 0))
    rect = block.boundingRect()
    assert rect.width() > 0
    assert rect.height() > 0
