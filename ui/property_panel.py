"""
선택된 블록의 속성(위치, 크기, 서식, 단위 표시 형식 등)을 보여주고
편집하는 사이드 패널.

블록 종류에 따라 관련 있는 항목만 보여준다 (예: 텍스트 블록에는
굵게/글자크기가, 이미지 블록에는 너비/높이가, 수식 블록에는 표시 단위가).
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from blocks.base_block import BaseBlock
from blocks.image_block import ImageBlock
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock

#: BLOCK_TYPE 문자열 -> 패널에 보여줄 한글 이름.
_TYPE_NAMES = {
    TextBlock.BLOCK_TYPE: "텍스트 블록",
    MathBlock.BLOCK_TYPE: "수식 블록",
    ImageBlock.BLOCK_TYPE: "이미지 블록",
}

_POSITION_RANGE = 100_000.0
_SIZE_RANGE = 100_000.0


class PropertyPanel(QWidget):
    """
    선택된 블록 하나의 속성을 보여주고, 값을 바꾸면 블록에 즉시 반영한다.

    사용 예:
        panel = PropertyPanel()
        panel.show_block(selected_block)  # 선택 해제 시 show_block(None)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._block: BaseBlock | None = None
        # 블록 -> 화면(위젯) 값을 채우는 동안에는, 그 값 변경이 다시
        # "사용자가 편집했다"는 신호로 오인되어 블록에 되먹임되면 안 된다.
        self._updating = False

        self._type_label = QLabel("(선택된 블록 없음)")

        self._x_spin = self._make_position_spin()
        self._y_spin = self._make_position_spin()
        self._width_spin = self._make_size_spin()
        self._height_spin = self._make_size_spin()
        self._bold_check = QCheckBox("굵게")
        self._font_size_spin = self._make_font_size_spin()
        self._unit_edit = QLineEdit()
        self._unit_edit.setPlaceholderText("예: MPa (비우면 자동 정리된 단위)")

        self._form = QFormLayout()
        self._form.addRow("종류", self._type_label)
        self._form.addRow("X", self._x_spin)
        self._form.addRow("Y", self._y_spin)
        self._form.addRow("너비", self._width_spin)
        self._form.addRow("높이", self._height_spin)
        self._form.addRow("", self._bold_check)
        self._form.addRow("글자 크기", self._font_size_spin)
        self._form.addRow("표시 단위", self._unit_edit)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)
        layout.addStretch()

        self._x_spin.valueChanged.connect(self._on_position_changed)
        self._y_spin.valueChanged.connect(self._on_position_changed)
        self._width_spin.valueChanged.connect(self._on_size_changed)
        self._height_spin.valueChanged.connect(self._on_size_changed)
        self._bold_check.toggled.connect(self._on_bold_changed)
        self._font_size_spin.valueChanged.connect(self._on_font_size_changed)
        self._unit_edit.editingFinished.connect(self._on_unit_changed)

        self.show_block(None)

    @staticmethod
    def _make_position_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-_POSITION_RANGE, _POSITION_RANGE)
        spin.setDecimals(1)
        return spin

    @staticmethod
    def _make_size_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(1.0, _SIZE_RANGE)
        spin.setDecimals(1)
        return spin

    @staticmethod
    def _make_font_size_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(6, 200)
        spin.setDecimals(0)
        return spin

    # --- 공개 API ---

    def show_block(self, block: BaseBlock | None) -> None:
        """패널에 표시할 블록을 바꾼다. None이면 "선택된 블록 없음" 상태로 비운다."""
        self._block = block
        self._updating = True
        try:
            self._refresh_fields()
        finally:
            self._updating = False

    def current_block(self) -> BaseBlock | None:
        """패널이 현재 보여주고 있는 블록."""
        return self._block

    # --- 내부: 블록 -> 화면 ---

    def _refresh_fields(self) -> None:
        block = self._block
        self.setEnabled(block is not None)

        if block is None:
            self._type_label.setText("(선택된 블록 없음)")
            for widget in (self._x_spin, self._y_spin, self._width_spin, self._height_spin, self._bold_check, self._font_size_spin, self._unit_edit):
                self._form.setRowVisible(widget, False)
            return

        self._type_label.setText(_TYPE_NAMES.get(block.BLOCK_TYPE, block.BLOCK_TYPE))
        self._x_spin.setValue(block.pos().x())
        self._y_spin.setValue(block.pos().y())
        self._form.setRowVisible(self._x_spin, True)
        self._form.setRowVisible(self._y_spin, True)

        is_image = isinstance(block, ImageBlock)
        self._form.setRowVisible(self._width_spin, is_image)
        self._form.setRowVisible(self._height_spin, is_image)
        if is_image:
            rect = block.boundingRect()
            self._width_spin.setValue(rect.width())
            self._height_spin.setValue(rect.height())

        is_text = isinstance(block, TextBlock)
        self._form.setRowVisible(self._bold_check, is_text)
        self._form.setRowVisible(self._font_size_spin, is_text)
        if is_text:
            self._bold_check.setChecked(block.is_bold())
            self._font_size_spin.setValue(block.font_size())

        is_math = isinstance(block, MathBlock)
        self._form.setRowVisible(self._unit_edit, is_math)
        if is_math:
            self._unit_edit.setText(block.preferred_unit())

    # --- 내부: 화면 -> 블록 ---

    def _on_position_changed(self, _value: float) -> None:
        if self._updating or self._block is None:
            return
        self._block.setPos(self._x_spin.value(), self._y_spin.value())

    def _on_size_changed(self, _value: float) -> None:
        if self._updating or not isinstance(self._block, ImageBlock):
            return
        self._block.set_size(self._width_spin.value(), self._height_spin.value())

    def _on_bold_changed(self, checked: bool) -> None:
        if self._updating or not isinstance(self._block, TextBlock):
            return
        self._block.set_bold(checked)

    def _on_font_size_changed(self, _value: float) -> None:
        if self._updating or not isinstance(self._block, TextBlock):
            return
        self._block.set_font_size(int(self._font_size_spin.value()))

    def _on_unit_changed(self) -> None:
        if self._updating or not isinstance(self._block, MathBlock):
            return
        self._block.set_preferred_unit(self._unit_edit.text())
