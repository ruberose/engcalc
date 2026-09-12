"""
수식/단위 편집창에서 쓰는 단위 자동완성 팝업.

blocks/math_block.py의 _InlineTextEditor/_UnitEditor는 QGraphicsTextItem
기반이라 일반 QWidget이 아니다 — 그래서 Qt의 QCompleter(QLineEdit 같은 진짜
위젯 대상으로 만들어짐)를 바로 붙일 수 없다. 대신 작은 QListWidget을 최상위
창으로 직접 띄우고, 방향키/Enter/Esc는 텍스트 편집창의 keyPressEvent가
가로채서 이 목록에 그대로 전달하는 식으로 자동완성을 흉내낸다 — 이 목록
자체는 절대 키보드 포커스를 가져가지 않는다(타이핑은 계속 편집창에서
일어나야 하므로, setFocusPolicy(NoFocus)).

Note:
    처음엔 Qt.WindowType.Popup을 썼는데, 실사용 중 "M을 치면 팝업이 뜨는데
    P를 이어 못 친다", "바깥을 눌러도 안 닫힌다", "Esc가 안 먹는다"는 문제가
    보고됐다. 원인을 재현해보니 Popup 창은 뜨는 순간 QApplication의
    "activePopupWidget"이 되어 OS 키보드 입력 자체를 가로채 버렸다(이후
    키 입력이 이 편집창까지 오지도 않음 — setFocusPolicy(NoFocus)는 포커스만
    막을 뿐 이 grab은 막지 못한다). Qt.WindowType.ToolTip은 항상 위에
    떠 있는 프레임 없는 창이면서도 이런 입력 가로채기가 없어서, 타이핑/Esc/
    바깥 클릭이 전부 편집창에 정상적으로 전달된다 — 직접 재현해서 확인함.
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
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
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

        # 과거 Qt.WindowType.Popup을 쓸 때, 네이티브 창이 아직 없는 "진짜 처음"
        # show()가 화면에 반영이 안 되고 두 번째 show()부터 정상 동작하는
        # 현상이 재현됐었다. ToolTip으로 바꾼 뒤로는 재현되지 않았지만, 두 번
        # 불러도 부작용이 없는 안전한 습관이라 그대로 남겨둔다. 이미 보이는
        # 중이면(타이핑하다 후보 목록만 갱신하는 흔한 경우) 다시 부르지 않는다.
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
