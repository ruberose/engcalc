"""canvas/document_scene.py의 to_blocks_list()/load_blocks_list() 왕복 테스트."""

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from blocks.image_block import ImageBlock
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene

_app = QApplication.instance() or QApplication([])


def test_round_trip_preserves_text_math_image_blocks():
    """텍스트/수식/이미지 블록을 모두 넣고 저장(dict화) -> 복원하면 그대로 돌아와야 한다."""
    scene = DocumentScene()

    text_block = TextBlock(position=(10, 10))
    text_block.set_text("1. 설계조건")
    scene.addItem(text_block)

    math_a = MathBlock(position=(10, 60))
    math_a.set_input_text("a = 100")
    scene.addItem(math_a)

    math_b = MathBlock(position=(10, 120))
    math_b.set_input_text("a * 2")
    scene.addItem(math_b)

    pixmap = QPixmap(30, 20)
    pixmap.fill(QColor(1, 2, 3))
    image_block = ImageBlock(position=(200, 10), pixmap=pixmap, caption="단면도")
    scene.addItem(image_block)

    scene.recalculate_all()
    assert not math_b._result.is_error
    assert float(math_b._result.value) == 200.0

    blocks_data = scene.to_blocks_list()
    assert len(blocks_data) == 4

    # 새 씬에 복원 (재계산까지 load_blocks_list 안에서 자동으로 일어남)
    restored_scene = DocumentScene()
    restored_scene.load_blocks_list(blocks_data)

    restored_items = restored_scene.items()
    assert len(restored_items) == 4

    restored_text = [i for i in restored_items if isinstance(i, TextBlock)][0]
    assert restored_text._text == "1. 설계조건"
    assert restored_text.pos().toTuple() == (10.0, 10.0)

    restored_math = sorted(
        (i for i in restored_items if isinstance(i, MathBlock)),
        key=lambda b: b.pos().y(),
    )
    assert restored_math[0].input_text() == "a = 100"
    assert restored_math[1].input_text() == "a * 2"
    # load_blocks_list()가 recalculate_all()까지 호출하므로 계산 결과도 복원돼야 한다.
    assert not restored_math[1]._result.is_error
    assert float(restored_math[1]._result.value) == 200.0

    restored_image = [i for i in restored_items if isinstance(i, ImageBlock)][0]
    assert restored_image._caption == "단면도"
    assert restored_image.boundingRect().width() == 30
    assert restored_image.boundingRect().height() == 20


def test_load_blocks_list_clears_existing_blocks():
    """load_blocks_list()를 호출하면 기존에 있던 블록은 모두 사라져야 한다 ("새로 만들기"/파일 열기 공용)."""
    scene = DocumentScene()
    scene.addItem(TextBlock(position=(0, 0)))
    assert len(scene.items()) == 1

    scene.load_blocks_list([])
    assert len(scene.items()) == 0


def test_load_blocks_list_skips_unknown_block_type():
    """알 수 없는 type은 조용히 건너뛰고 나머지는 정상 복원해야 한다."""
    scene = DocumentScene()
    blocks_data = [
        {"type": "text", "id": "blk_1", "position": [0.0, 0.0], "content": "hello", "style": {"font_size": 14, "bold": False}},
        {"type": "unknown_future_block", "id": "blk_2", "position": [0.0, 0.0]},
    ]
    scene.load_blocks_list(blocks_data)
    assert len(scene.items()) == 1
