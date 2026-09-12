"""
blocks/math_block.py — 수식 블록 글자 크기 조절 기능 검증.

사용자 요청: "글자 사이즈 조절 기능도 넣어줘" — 텍스트 블록은 이미 있었지만
수식 블록은 INPUT_FONT_SIZE가 전역 상수라 블록마다 따로 조절할 수 없었다.
텍스트 블록의 font_size()/set_font_size() 패턴을 그대로 따라 추가했다.
"""

from PySide6.QtWidgets import QApplication

from blocks.math_block import INPUT_FONT_SIZE, MathBlock
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


def test_default_font_size_matches_module_constant():
    block = MathBlock(position=(0, 0))
    assert block.font_size() == INPUT_FONT_SIZE


def test_set_font_size_updates_getter():
    block = MathBlock(position=(0, 0))
    block.set_font_size(24)
    assert block.font_size() == 24


def test_set_font_size_changes_bounding_rect():
    """글자를 키우면 렌더링된 픽스맵이 커져서 boundingRect도 커져야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    small_rect = block.boundingRect()

    block.set_font_size(40)
    large_rect = block.boundingRect()

    assert large_rect.width() > small_rect.width()
    assert large_rect.height() > small_rect.height()


def test_set_font_size_rerenders_input_pixmap():
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    original_pixmap = block._input_pixmap
    assert original_pixmap is not None

    block.set_font_size(40)

    assert block._input_pixmap is not None
    assert block._input_pixmap.height() > original_pixmap.height()


def test_set_font_size_rerenders_combined_line_after_evaluation():
    scope = Scope()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1 + 1")
    block.evaluate(scope)
    original = block._combined_pixmap
    assert original is not None

    block.set_font_size(36)

    assert block._combined_pixmap is not None
    assert block._combined_pixmap.height() > original.height()


def test_font_size_round_trips_through_serialize():
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    block.set_font_size(18)

    data = block.serialize()
    assert data["font_size"] == 18

    restored = MathBlock(position=(0, 0))
    restored.deserialize(data)
    assert restored.font_size() == 18


def test_loading_old_block_data_without_font_size_defaults_to_module_constant():
    """글자 크기 필드가 없는 옛 파일(하위 호환)은 기본 크기로 열려야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    data = block.serialize()
    del data["font_size"]

    restored = MathBlock(position=(0, 0))
    restored.deserialize(data)
    assert restored.font_size() == INPUT_FONT_SIZE


def test_font_size_change_does_not_affect_computation():
    """글자 크기는 표시 전용이므로, 계산 결과 자체는 바뀌면 안 된다."""
    scope = Scope()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 5 * 2")
    block.evaluate(scope)
    original_value = block.result().value

    block.set_font_size(32)
    block.evaluate(scope)

    assert block.result().value == original_value
