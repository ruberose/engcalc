"""
수식 블록 결과 표시 자릿수(속성 패널 "표시 자릿수") 기능 검증.

사용자 요청: 결과가 항상 정해진 자릿수(유효숫자 6개)로만 보이는데, "1.333333"
대신 "1.33"처럼 원하는 만큼만 보이게 하고 싶다. 표시 단위(preferred_unit)와
같은 패턴 — 계산값 자체는 안 바뀌고 보여주는 방식만 바뀐다.
"""

from PySide6.QtWidgets import QApplication

from blocks.math_block import MathBlock, format_value
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


def test_default_decimal_places_is_auto():
    block = MathBlock(position=(0, 0))
    assert block.decimal_places() == -1


def test_set_decimal_places_updates_getter():
    block = MathBlock(position=(0, 0))
    block.set_decimal_places(2)
    assert block.decimal_places() == 2


def test_set_decimal_places_none_reverts_to_auto():
    block = MathBlock(position=(0, 0))
    block.set_decimal_places(2)
    block.set_decimal_places(None)
    assert block.decimal_places() == -1


def test_decimal_places_formats_result_with_fixed_digits():
    scope = Scope()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1 / 3")
    block.evaluate(scope)
    block.set_decimal_places(2)

    assert block.result_value_text() == "0.33"


def test_decimal_places_zero_shows_no_fraction():
    scope = Scope()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 10 / 3")
    block.evaluate(scope)
    block.set_decimal_places(0)

    assert block.result_value_text() == "3"


def test_decimal_places_auto_keeps_existing_behavior():
    scope = Scope()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 6")
    block.evaluate(scope)

    assert block.result_value_text() == "6"


def test_decimal_places_does_not_affect_computation():
    scope = Scope()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 5 / 2")
    block.evaluate(scope)
    original_value = block.result().value

    block.set_decimal_places(1)
    block.evaluate(scope)

    assert block.result().value == original_value


def test_decimal_places_round_trips_through_serialize():
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    block.set_decimal_places(3)

    data = block.serialize()
    assert data["decimal_places"] == 3

    restored = MathBlock(position=(0, 0))
    restored.deserialize(data)
    assert restored.decimal_places() == 3


def test_loading_old_block_data_without_decimal_places_defaults_to_auto():
    """자릿수 필드가 없는 옛 파일(하위 호환)은 자동 표시로 열려야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    data = block.serialize()
    del data["decimal_places"]

    restored = MathBlock(position=(0, 0))
    restored.deserialize(data)
    assert restored.decimal_places() == -1


def test_format_value_with_decimal_places_and_unit():
    from engine.unit_manager import ureg

    value = 1.0 / 3 * ureg.meter

    assert format_value(value, decimal_places=2) == "0.33 m"


def test_format_value_without_decimal_places_uses_existing_rule():
    assert format_value(1.0 / 3) == "0.333333"
