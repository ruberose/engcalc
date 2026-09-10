"""
MathBlock의 "PPT 글상자 스타일" 표시 테스트: 기본은 한 줄, 손잡이로 폭을
좁히면 입력/결과 두 줄로 접힌다.
"""

from PySide6.QtWidgets import QApplication

from blocks.math_block import MathBlock
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


def _block_with_result(text: str, scope: Scope | None = None) -> MathBlock:
    block = MathBlock(position=(0, 0))
    block.set_input_text(text)
    block.evaluate(scope if scope is not None else Scope())
    return block


def test_expression_result_combines_into_one_line_by_default():
    """"A + B"처럼 결과가 따로 필요한 식은 기본적으로 "입력 = 결과" 한 줄로 합쳐져야 한다."""
    scope = Scope()
    _block_with_result("A = 5 m", scope)
    _block_with_result("B = 10 m", scope)
    block = _block_with_result("A + B", scope)

    assert block._one_line_mode is True
    assert block._combined_line_text() == "A + B = 15 m"


def test_literal_assignment_is_already_one_line():
    """"a = 100"은 원래도 한 줄이었고, 계속 한 줄이어야 한다(합칠 결과가 따로 없음)."""
    block = _block_with_result("a = 100")
    assert block._one_line_mode is True
    assert block._combined_line_text() == "a = 100"


def test_narrow_manual_width_wraps_to_two_lines():
    """폭을 내용보다 좁게 지정하면(손잡이로 줄인 상황을 흉내) 두 줄로 바뀌어야 한다."""
    scope = Scope()
    _block_with_result("A = 5 m", scope)
    _block_with_result("B = 10 m", scope)
    block = _block_with_result("A + B", scope)

    natural_width = block.boundingRect().width()
    block.set_manual_width(natural_width / 2)  # 한 줄로 담기엔 확실히 좁게

    assert block._one_line_mode is False
    # 줄바꿈은 "보여주는 방식"만 바꿀 뿐, 계산 결과 자체는 그대로여야 한다.
    assert not block.result().is_error
    assert block.result().value is not None


def test_widening_back_returns_to_one_line():
    """좁혔다가 다시 넓히면(또는 자동으로 되돌리면) 한 줄로 돌아와야 한다."""
    scope = Scope()
    _block_with_result("A = 5 m", scope)
    _block_with_result("B = 10 m", scope)
    block = _block_with_result("A + B", scope)

    block.set_manual_width(50)
    assert block._one_line_mode is False

    block.set_manual_width(None)  # 자동 크기로 복귀
    assert block._one_line_mode is True


def test_manual_width_round_trips_through_serialize():
    """손잡이로 지정한 폭도 저장/복원되어야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 100")
    block.set_manual_width(150)

    data = block.serialize()
    assert data["width"] == 150

    restored = MathBlock()
    restored.deserialize(data)
    assert restored.manual_width() == 150


def test_no_manual_width_is_not_saved():
    """폭을 지정한 적 없으면 저장 데이터에 "width" 필드 자체가 없어야 한다(항상 자동 한 줄)."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 100")
    data = block.serialize()
    assert "width" not in data
