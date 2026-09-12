"""ui/property_panel.py 단위 테스트."""

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from blocks.image_block import ImageBlock
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from engine.scope import Scope
from ui.property_panel import PropertyPanel

_app = QApplication.instance() or QApplication([])


def test_show_block_none_disables_panel():
    """선택된 블록이 없으면 패널이 비활성화되고 안내 문구만 보여야 한다."""
    panel = PropertyPanel()
    panel.show_block(None)
    assert panel.isEnabled() is False
    assert panel.current_block() is None


def test_show_text_block_populates_fields():
    """텍스트 블록을 보여주면 위치/굵기/글자크기가 채워져야 한다."""
    block = TextBlock(position=(50, 60))
    block.set_bold(True)
    block.set_font_size(20)

    panel = PropertyPanel()
    panel.show_block(block)

    assert panel._x_spin.value() == 50
    assert panel._y_spin.value() == 60
    assert panel._bold_check.isChecked() is True
    assert panel._font_size_spin.value() == 20


def test_editing_position_moves_block():
    """X/Y 값을 바꾸면 블록이 실제로 그 위치로 이동해야 한다."""
    block = TextBlock(position=(0, 0))
    panel = PropertyPanel()
    panel.show_block(block)

    panel._x_spin.setValue(123)
    panel._y_spin.setValue(456)

    assert block.pos().x() == 123
    assert block.pos().y() == 456


def test_editing_bold_and_font_size_updates_text_block():
    """굵게 체크박스/글자크기를 바꾸면 블록에 즉시 반영되어야 한다."""
    block = TextBlock(position=(0, 0))
    panel = PropertyPanel()
    panel.show_block(block)

    panel._bold_check.setChecked(True)
    panel._font_size_spin.setValue(30)

    assert block.is_bold() is True
    assert block.font_size() == 30


def test_editing_size_resizes_image_block():
    """이미지 블록의 너비/높이를 바꾸면 실제 크기가 바뀌어야 한다."""
    pixmap = QPixmap(40, 20)
    pixmap.fill(QColor(1, 2, 3))
    block = ImageBlock(position=(0, 0), pixmap=pixmap)

    panel = PropertyPanel()
    panel.show_block(block)
    assert panel._width_spin.value() == 40
    assert panel._height_spin.value() == 20

    panel._width_spin.setValue(200)
    panel._height_spin.setValue(150)

    assert block.boundingRect().width() == 200
    assert block.boundingRect().height() == 150


def test_show_math_block_populates_font_size_field():
    """수식 블록도 텍스트 블록처럼 글자 크기 필드가 채워져야 한다(굵게는 지원 안 함)."""
    block = MathBlock(position=(0, 0))
    block.set_font_size(22)

    panel = PropertyPanel()
    panel.show_block(block)

    assert panel._form.isRowVisible(panel._font_size_spin) is True
    assert panel._font_size_spin.value() == 22
    assert panel._form.isRowVisible(panel._bold_check) is False


def test_editing_font_size_updates_math_block():
    """글자크기를 바꾸면 수식 블록에도 즉시 반영되어야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    panel = PropertyPanel()
    panel.show_block(block)

    panel._font_size_spin.setValue(28)

    assert block.font_size() == 28


def test_editing_unit_updates_math_block_display():
    """수식 블록의 표시 단위를 바꾸면 결과가 그 단위로 다시 표시되어야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("F = 200000 Pa")
    scope = Scope()
    block.evaluate(scope)

    panel = PropertyPanel()
    panel.show_block(block)
    assert panel._unit_edit.text() == ""

    panel._unit_edit.setText("kPa")
    panel._unit_edit.editingFinished.emit()

    assert block.preferred_unit() == "kPa"


def test_show_math_block_populates_decimal_places_field():
    """수식 블록에는 표시 자릿수 필드가 보이고, 지정 안 했으면 자동(-1)이어야 한다."""
    block = MathBlock(position=(0, 0))

    panel = PropertyPanel()
    panel.show_block(block)

    assert panel._form.isRowVisible(panel._decimal_places_spin) is True
    assert panel._decimal_places_spin.value() == -1


def test_text_block_hides_decimal_places_field():
    block = TextBlock(position=(0, 0))

    panel = PropertyPanel()
    panel.show_block(block)

    assert panel._form.isRowVisible(panel._decimal_places_spin) is False


def test_editing_decimal_places_updates_math_block():
    """자릿수를 바꾸면 수식 블록에도 즉시 반영되어야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1 / 3")
    scope = Scope()
    block.evaluate(scope)

    panel = PropertyPanel()
    panel.show_block(block)

    panel._decimal_places_spin.setValue(2)

    assert block.decimal_places() == 2
    assert block.result_value_text() == "0.33"


def test_setting_decimal_places_back_to_auto_clears_it():
    block = MathBlock(position=(0, 0))
    block.set_decimal_places(3)

    panel = PropertyPanel()
    panel.show_block(block)

    panel._decimal_places_spin.setValue(-1)

    assert block.decimal_places() == -1


def test_switching_block_type_hides_irrelevant_fields():
    """블록 종류를 바꿔가며 보여주면, 관련 없는 행은 숨겨져야 한다 (form.isRowVisible)."""
    text_block = TextBlock(position=(0, 0))
    image_block = ImageBlock(position=(0, 0))

    panel = PropertyPanel()

    panel.show_block(text_block)
    assert panel._form.isRowVisible(panel._bold_check) is True
    assert panel._form.isRowVisible(panel._width_spin) is False

    panel.show_block(image_block)
    assert panel._form.isRowVisible(panel._bold_check) is False
    assert panel._form.isRowVisible(panel._width_spin) is True
