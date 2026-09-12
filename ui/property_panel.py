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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from blocks.base_block import BaseBlock
from blocks.image_block import ImageBlock
from blocks.math_block import MathBlock
from blocks.table_block import TableBlock
from blocks.text_block import TextBlock

#: BLOCK_TYPE 문자열 -> 패널에 보여줄 한글 이름.
_TYPE_NAMES = {
    TextBlock.BLOCK_TYPE: "텍스트 블록",
    MathBlock.BLOCK_TYPE: "수식 블록",
    ImageBlock.BLOCK_TYPE: "이미지 블록",
    TableBlock.BLOCK_TYPE: "표 블록",
}

_TABLE_SIZE_RANGE = (1, 50)

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
        self._decimal_places_spin = self._make_decimal_places_spin()
        self._rows_spin = self._make_table_size_spin()
        self._cols_spin = self._make_table_size_spin()

        self._form = QFormLayout()
        self._form.addRow("종류", self._type_label)
        self._form.addRow("X", self._x_spin)
        self._form.addRow("Y", self._y_spin)
        self._form.addRow("너비", self._width_spin)
        self._form.addRow("높이", self._height_spin)
        self._form.addRow("", self._bold_check)
        self._form.addRow("글자 크기", self._font_size_spin)
        self._form.addRow("표시 단위", self._unit_edit)
        self._form.addRow("표시 자릿수", self._decimal_places_spin)
        self._form.addRow("행 수", self._rows_spin)
        self._form.addRow("열 수", self._cols_spin)

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
        self._decimal_places_spin.valueChanged.connect(self._on_decimal_places_changed)
        self._rows_spin.valueChanged.connect(self._on_row_count_changed)
        self._cols_spin.valueChanged.connect(self._on_col_count_changed)

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

    @staticmethod
    def _make_decimal_places_spin() -> QSpinBox:
        """-1(특수값 "자동")부터 15까지의 정수 스핀박스 — 수식 블록의 결과 표시 자릿수용."""
        spin = QSpinBox()
        spin.setRange(-1, 15)
        spin.setSpecialValueText("자동")
        return spin

    @staticmethod
    def _make_table_size_spin() -> QSpinBox:
        """표 블록의 행/열 수 조절용 정수 스핀박스."""
        spin = QSpinBox()
        spin.setRange(*_TABLE_SIZE_RANGE)
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
            for widget in (
                self._x_spin,
                self._y_spin,
                self._width_spin,
                self._height_spin,
                self._bold_check,
                self._font_size_spin,
                self._unit_edit,
                self._decimal_places_spin,
                self._rows_spin,
                self._cols_spin,
            ):
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
        is_math = isinstance(block, MathBlock)
        is_table = isinstance(block, TableBlock)

        # 굵게는 텍스트 블록만 지원한다(수식은 mathtext 렌더링이라 별도 지원 없음).
        self._form.setRowVisible(self._bold_check, is_text)
        if is_text:
            self._bold_check.setChecked(block.is_bold())

        # 글자 크기는 텍스트/수식/표 블록 모두 지원한다.
        self._form.setRowVisible(self._font_size_spin, is_text or is_math or is_table)
        if is_text or is_math or is_table:
            self._font_size_spin.setValue(block.font_size())

        self._form.setRowVisible(self._unit_edit, is_math)
        if is_math:
            self._unit_edit.setText(block.preferred_unit())

        self._form.setRowVisible(self._decimal_places_spin, is_math)
        if is_math:
            self._decimal_places_spin.setValue(block.decimal_places())

        self._form.setRowVisible(self._rows_spin, is_table)
        self._form.setRowVisible(self._cols_spin, is_table)
        if is_table:
            self._rows_spin.setValue(block.row_count())
            self._cols_spin.setValue(block.col_count())

    # --- 내부: 화면 -> 블록 ---

    def _apply_with_undo(self, mutate, recalc: bool = False) -> None:
        """
        블록을 바꾸는 동작(mutate)을 실행하고, 실제로 뭔가 달라졌으면 실행취소에 기록한다.

        Args:
            mutate: 블록 속성을 실제로 바꾸는 인자 없는 콜러블.
            recalc: True면 변경 후 scene.recalculate_all()도 호출한다(위치 변경처럼
                계산 순서에 영향을 줄 수 있는 경우만 — 굵게/글자크기/단위 표시 같은
                건 계산에 영향이 없으므로 기본값 False로 둔다).
        """
        scene = self._block.scene() if self._block is not None else None
        before = scene.capture_undo_snapshot() if scene is not None and hasattr(scene, "capture_undo_snapshot") else None

        mutate()

        if scene is None:
            return
        if before is not None and hasattr(scene, "commit_undo_snapshot"):
            scene.commit_undo_snapshot(before)
        if recalc and hasattr(scene, "recalculate_all"):
            scene.recalculate_all()

    def _on_position_changed(self, _value: float) -> None:
        if self._updating or self._block is None:
            return
        # 블록은 화면 위→아래 순서로 계산되므로(계획서 5.1), 여기서 위치를 바꿔
        # 순서가 뒤집히면 재계산해야 한다. 마우스로 드래그할 때는 BaseBlock이
        # 드래그가 "끝날 때" 한 번만 재계산하지만(blocks/base_block.py), 이 스핀박스는
        # 마우스 이벤트를 거치지 않고 setPos()를 직접 호출하므로 그 경로를 안 탄다
        # — 그래서 여기서 직접 요청해야 한다(버그체크 중 발견).
        self._apply_with_undo(
            lambda: self._block.setPos(self._x_spin.value(), self._y_spin.value()), recalc=True
        )

    def _on_size_changed(self, _value: float) -> None:
        if self._updating or not isinstance(self._block, ImageBlock):
            return
        self._apply_with_undo(lambda: self._block.set_size(self._width_spin.value(), self._height_spin.value()))

    def _on_bold_changed(self, checked: bool) -> None:
        if self._updating or not isinstance(self._block, TextBlock):
            return
        self._apply_with_undo(lambda: self._block.set_bold(checked))

    def _on_font_size_changed(self, _value: float) -> None:
        if self._updating or not isinstance(self._block, (TextBlock, MathBlock, TableBlock)):
            return
        self._apply_with_undo(lambda: self._block.set_font_size(int(self._font_size_spin.value())))

    def _on_unit_changed(self) -> None:
        if self._updating or not isinstance(self._block, MathBlock):
            return
        self._apply_with_undo(lambda: self._block.set_preferred_unit(self._unit_edit.text()))

    def _on_decimal_places_changed(self, value: int) -> None:
        if self._updating or not isinstance(self._block, MathBlock):
            return
        places = value if value >= 0 else None
        self._apply_with_undo(lambda: self._block.set_decimal_places(places))

    def _on_row_count_changed(self, value: int) -> None:
        if self._updating or not isinstance(self._block, TableBlock):
            return
        self._apply_with_undo(lambda: self._block.set_row_count(value))

    def _on_col_count_changed(self, value: int) -> None:
        if self._updating or not isinstance(self._block, TableBlock):
            return
        self._apply_with_undo(lambda: self._block.set_col_count(value))
