"""
캔버스에서 블록을 검색하는 찾기 대화상자 (메뉴 > 편집 > 찾기, Ctrl+F).

수식/텍스트 블록의 내용, 이미지 캡션에서 검색어를 찾아 그 블록으로 화면을
이동시키고 선택 상태로 만든다. 실제 검색 로직(canvas/document_scene.py의
find_blocks())은 이 창이 아니라 씬이 가지고 있다 — 이 창은 검색어 입력과
"이전/다음" 이동만 담당한다(모듈 분리 원칙).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from blocks.base_block import BaseBlock
from canvas.document_scene import DocumentScene
from canvas.document_view import DocumentView


class FindDialog(QDialog):
    """
    캔버스 블록 찾기 대화상자.

    Note:
        비모달(show())로 띄워서, 검색 결과를 캔버스에서 눈으로 확인하면서
        계속 검색어를 바꾸거나 "다음"을 누를 수 있게 한다.
    """

    def __init__(self, scene: DocumentScene, view: DocumentView, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("찾기")
        self.resize(360, 110)

        self._scene = scene
        self._view = view
        self._matches: list[BaseBlock] = []
        self._current_index = -1

        self._input = QLineEdit()
        self._input.setPlaceholderText("찾을 내용 입력 (수식/텍스트/이미지 캡션)")
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self.find_next)

        self._status_label = QLabel("")

        prev_button = QPushButton("이전")
        prev_button.clicked.connect(self.find_previous)
        next_button = QPushButton("다음")
        next_button.clicked.connect(self.find_next)
        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.close)

        button_row = QHBoxLayout()
        button_row.addWidget(self._status_label)
        button_row.addStretch()
        button_row.addWidget(prev_button)
        button_row.addWidget(next_button)
        button_row.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._input)
        layout.addLayout(button_row)

    def focus_input(self) -> None:
        """검색창에 포커스를 주고 기존 텍스트를 전체 선택한다 (다시 열었을 때 바로 새로 칠 수 있게)."""
        self._input.setFocus()
        self._input.selectAll()

    def find_next(self) -> None:
        """다음 검색 결과로 이동한다 (마지막이면 처음으로 돌아감)."""
        if not self._matches:
            return
        self._go_to((self._current_index + 1) % len(self._matches))

    def find_previous(self) -> None:
        """이전 검색 결과로 이동한다 (처음이면 마지막으로 돌아감)."""
        if not self._matches:
            return
        self._go_to((self._current_index - 1) % len(self._matches))

    def _on_text_changed(self, text: str) -> None:
        """타이핑할 때마다 바로 다시 검색한다."""
        self._matches = self._scene.find_blocks(text)
        self._current_index = -1
        if self._matches:
            self._go_to(0)
        else:
            self._scene.clearSelection()
            self._status_label.setText("검색 결과 없음" if text.strip() else "")

    def _go_to(self, index: int) -> None:
        """index번째 검색 결과 블록을 선택하고 화면 중앙으로 이동시킨다."""
        self._current_index = index
        block = self._matches[index]
        self._scene.clearSelection()
        block.setSelected(True)
        self._view.centerOn(block)
        self._status_label.setText(f"{index + 1} / {len(self._matches)}")
