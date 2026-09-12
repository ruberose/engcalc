"""
수식/단위 편집창에서 쓰는 단위 자동완성 팝업.

blocks/math_block.py의 _InlineTextEditor/_UnitEditor는 QGraphicsTextItem
기반이라 일반 QWidget이 아니다 — 그래서 Qt의 QCompleter(QLineEdit 같은 진짜
위젯 대상으로 만들어짐)를 바로 붙일 수 없다. 대신 작은 QListWidget을
Qt.Popup 창으로 직접 띄우고, 방향키/Enter/Esc는 텍스트 편집창의
keyPressEvent가 가로채서 이 목록에 그대로 전달하는 식으로 자동완성을
흉내낸다 — 이 목록 자체는 절대 키보드 포커스를 가져가지 않는다(타이핑은
계속 편집창에서 일어나야 하므로, setFocusPolicy(NoFocus)).
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QListWidget

from engine.unit_manager import KNOWN_UNIT_NAMES

_ITEM_HEIGHT = 22
_MAX_VISIBLE_ITEMS = 8
_POPUP_WIDTH = 120


class UnitSuggestionPopup(QListWidget):
    """단위 이름 후보를 보여주는 작은 팝업 목록."""

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setUniformItemSizes(True)

    def show_matches(self, query: str, global_pos: QPoint) -> bool:
        """
        query로 시작하는(대소문자 구분 없음) 단위 후보를 global_pos 위치에 띄운다.

        Returns:
            후보가 있어서 실제로 띄웠으면 True, 후보가 없거나(또는 유일한
            후보가 이미 완전히 입력된 상태라 더 완성할 게 없으면) 숨기고 False.
        """
        query_lower = query.lower()
        matches = [name for name in KNOWN_UNIT_NAMES if name.lower().startswith(query_lower)]
        if not matches or (len(matches) == 1 and matches[0].lower() == query_lower):
            self.hide()
            return False

        self.clear()
        self.addItems(matches)
        self.setCurrentRow(0)

        # Qt.WindowType.Popup 창은 두 가지 특이 동작이 직접 재현해서 확인됐다:
        # (a) 네이티브 창이 아직 없는 "진짜 처음" show()는 화면에 반영이 안
        #     되고, 두 번째 show()부터 정상 동작한다.
        # (b) 반대로 "이미 떠 있는" 상태에서 show()를 또 부르면 오히려
        #     닫혀버린다(Qt의 팝업 grab 처리와 관련된 것으로 보임).
        # 그래서 "아직 안 보일 때만" 두 번 불러서 확실히 띄우고, 이미 보이는
        # 중이면(타이핑하다 후보 목록만 갱신하는 흔한 경우) show()를 아예
        # 다시 부르지 않는다.
        if not self.isVisible():
            self.show()
            self.show()
        self.move(global_pos)
        visible_rows = min(_MAX_VISIBLE_ITEMS, len(matches))
        self.resize(_POPUP_WIDTH, _ITEM_HEIGHT * visible_rows + 4)
        return True

    def move_selection(self, delta: int) -> None:
        """선택된 후보를 위/아래로 옮긴다 (delta=+1 다음, -1 이전, 양 끝에서 순환)."""
        if self.count() == 0:
            return
        self.setCurrentRow((self.currentRow() + delta) % self.count())

    def selected_text(self) -> str | None:
        """지금 선택된 후보 텍스트. 후보가 없으면 None."""
        item = self.currentItem()
        return item.text() if item is not None else None
