"""
문서 속성(제목/작성자, 머리글·바닥글 표시 여부)을 편집하는 대화상자.

메뉴 > 파일 > 문서 속성... 에서 연다. 여기서 정한 값은 파일에 저장되어
문서마다 따로 유지되고(app/main_window.py의 _save_to_path()/_write_autosave()
참고), PDF로 내보내기/인쇄의 머리글(제목+작성자+날짜)/바닥글(쪽 번호)에
반영된다 — file_io/pdf_exporter.py가 실제 그리기를 담당한다.
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class DocumentPropertiesDialog(QDialog):
    """문서 제목/작성자와 PDF·인쇄 머리글/바닥글 표시 여부를 편집하는 대화상자."""

    def __init__(
        self,
        title: str = "",
        author: str = "",
        show_header_footer: bool = False,
        default_title_hint: str = "",
        parent=None,
    ) -> None:
        """
        Args:
            title: 지금 설정된 문서 제목 (비어 있으면 파일명을 대신 씀)
            author: 지금 설정된 작성자
            show_header_footer: PDF/인쇄에 머리글·바닥글을 표시할지
            default_title_hint: 제목을 안 정했을 때 대신 쓰일 이름(보통 파일명) —
                입력칸의 placeholder로만 보여줘서, 지금 뭐가 기본값으로 쓰이는지 알려준다.
        """
        super().__init__(parent)
        self.setWindowTitle("문서 속성")
        self.resize(360, 160)

        self._title_input = QLineEdit(title)
        self._title_input.setPlaceholderText(default_title_hint or "(비우면 파일명을 사용)")

        self._author_input = QLineEdit(author)
        self._author_input.setPlaceholderText("(선택 사항)")

        self._show_header_footer_checkbox = QCheckBox("PDF로 내보내기/인쇄 시 머리글·바닥글 표시")
        self._show_header_footer_checkbox.setChecked(show_header_footer)

        form = QFormLayout()
        form.addRow("제목", self._title_input)
        form.addRow("작성자", self._author_input)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._show_header_footer_checkbox)
        layout.addStretch()
        layout.addWidget(button_box)

    def result_properties(self) -> tuple[str, str, bool]:
        """입력된 (제목, 작성자, 머리글·바닥글 표시 여부)를 돌려준다. 제목/작성자는 앞뒤 공백을 정리한다."""
        return (
            self._title_input.text().strip(),
            self._author_input.text().strip(),
            self._show_header_footer_checkbox.isChecked(),
        )
