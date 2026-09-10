"""
현재 문서에 정의된 변수 목록을 보여주는 사이드 패널.

DocumentScene.variables_changed 신호를 구독해서, 재계산이 일어날 때마다
목록을 새로 그린다. 변수를 더블클릭하면 그 변수를 정의한 수식 블록으로
캔버스가 이동하도록 block_activated 신호를 내보낸다 (실제로 스크롤을
움직이는 건 이 신호를 구독하는 app/main_window.py의 몫이다).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from blocks.math_block import MathBlock, format_value
from canvas.document_scene import DocumentScene

#: 변수 이름을 리스트 아이템에 함께 저장해둘 때 쓰는 데이터 role.
_NAME_ROLE = Qt.ItemDataRole.UserRole


class VariableInspector(QWidget):
    """
    변수 이름 -> 값 목록.

    사용 예:
        inspector = VariableInspector()
        inspector.set_scene(document_scene)
        inspector.block_activated.connect(lambda block: view.centerOn(block))
    """

    #: 변수 항목을 더블클릭하면, 그 변수를 정의한 MathBlock을 실어 보낸다.
    block_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._scene: DocumentScene | None = None

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list)

    def set_scene(self, scene: DocumentScene) -> None:
        """추적할 씬을 지정한다. 씬이 재계산될 때마다 목록을 자동으로 새로 그린다."""
        if self._scene is not None:
            self._scene.variables_changed.disconnect(self.refresh)
        self._scene = scene
        self._scene.variables_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        """현재 씬의 변수 목록으로 다시 그린다."""
        self._list.clear()
        if self._scene is None:
            return

        for name, value in self._scene.variables().items():
            item = QListWidgetItem(f"{name} = {format_value(value)}")
            item.setData(_NAME_ROLE, name)
            self._list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        if self._scene is None:
            return
        name = item.data(_NAME_ROLE)
        block = self._scene.block_for_variable(name)
        if isinstance(block, MathBlock):
            self.block_activated.emit(block)
