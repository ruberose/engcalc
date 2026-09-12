"""
새 문서를 만들 때 문서 형식을 고르는 대화상자 (메뉴 > 파일 > 새로 만들기).

한글/워드처럼 "자유 캔버스"와 "용지 기반(A4 등)" 중 하나를 고르게 한다.
형식은 새 문서를 만드는 이 시점에만 정하고, 만든 뒤에는 바꾸는 UI가 따로
없다 — canvas/document_scene.py의 DocumentScene.set_document_format()이
실제 형식을 적용하는 쪽이고, 이 대화상자는 사용자의 선택만 모아서 돌려준다.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from canvas.document_scene import PAPER_SIZES_MM


class NewDocumentDialog(QDialog):
    """새 문서의 형식(자유 캔버스 / 용지 기반)과 용지 크기를 고르는 대화상자."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("새 문서")
        self.resize(320, 160)

        self._freeform_radio = QRadioButton("자유 캔버스 (기존 방식)")
        self._freeform_radio.setChecked(True)
        self._paper_radio = QRadioButton("문서 (용지 기반)")

        self._paper_size_combo = QComboBox()
        self._paper_size_combo.addItems(sorted(PAPER_SIZES_MM.keys()))
        self._paper_size_combo.setEnabled(False)
        self._paper_radio.toggled.connect(self._paper_size_combo.setEnabled)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("만들 문서의 형식을 고르세요:"))
        layout.addWidget(self._freeform_radio)
        layout.addWidget(self._paper_radio)
        layout.addWidget(self._paper_size_combo)
        layout.addStretch()
        layout.addWidget(button_box)

    def result_format(self) -> tuple[str, str]:
        """
        선택된 (document_format, paper_size)를 돌려준다.

        Returns:
            자유 캔버스를 골랐으면 ("freeform", "A4"), 용지 기반을 골랐으면
            ("paper", 선택된 용지 이름) — 용지 이름은 항상 PAPER_SIZES_MM에 있는 값이다.
        """
        if self._paper_radio.isChecked():
            return "paper", self._paper_size_combo.currentText()
        return "freeform", "A4"
