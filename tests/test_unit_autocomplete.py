"""
단위 자동완성 기능 검증 (blocks/unit_suggestion_popup.py,
blocks/math_block.py의 _InlineTextEditor/_UnitEditor).

사용자 요청: "단위 입력 자동완성... 이거도 만들자"

QGraphicsTextItem 편집창은 일반 위젯이 아니라 QCompleter를 바로 못 붙이므로,
직접 만든 작은 팝업(UnitSuggestionPopup)과 방향키/Enter/Esc 가로채기로
자동완성을 흉내낸다. 여기서는 (1) 팝업 자체의 필터링/이동 로직과,
(2) 수식 블록 편집창에서 실제로 이 팝업이 뜨고 선택을 반영하는지를 검증한다.
"""

import gc

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from blocks.math_block import _TRAILING_UNIT_TOKEN, MathBlock, _InlineTextEditor, _UnitEditor
from blocks.unit_suggestion_popup import UnitSuggestionPopup
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


@pytest.fixture
def window():
    """테스트용 MainWindow 하나 (정리 방식은 test_recalculation_triggers.py의 동일 fixture 참고)."""
    win = MainWindow()
    win.show()
    for _ in range(3):
        _app.processEvents()
    yield win
    win._scene.selectionChanged.disconnect(win._on_selection_changed)
    win._scene.changed.disconnect(win._on_scene_changed)
    win._autosave_timer.stop()
    win._is_modified = False
    win.close()
    _app.processEvents()
    del win
    gc.collect()
    _app.processEvents()


# --- UnitSuggestionPopup ---


def test_show_matches_filters_by_prefix_case_insensitive():
    """대소문자 구분 없이 접두어가 일치하는 후보만 보여줘야 한다."""
    popup = UnitSuggestionPopup()
    shown = popup.show_matches("k", QPoint(0, 0))
    assert shown
    items = [popup.item(i).text() for i in range(popup.count())]
    assert "kN" in items
    assert "kg" in items
    assert "kPa" in items
    assert "m" not in items  # "m"은 "k"로 시작 안 하므로 후보에서 빠져야 함
    popup.close()


def test_show_matches_hides_when_no_match():
    """일치하는 단위가 하나도 없으면 숨기고 False를 돌려줘야 한다."""
    popup = UnitSuggestionPopup()
    assert popup.show_matches("존재하지않는단위xyz", QPoint(0, 0)) is False
    assert not popup.isVisible()
    popup.close()


def test_show_matches_hides_when_only_match_already_fully_typed():
    """유일한 후보가 이미 입력한 것과 똑같으면(더 완성할 게 없으면) 숨겨야 한다."""
    popup = UnitSuggestionPopup()
    # "psi"로 시작하는 후보는 "psi" 자신뿐이므로(ksi는 "k"로 시작), 이미 다 친 것과 같다.
    assert popup.show_matches("psi", QPoint(0, 0)) is False
    popup.close()


def test_move_selection_wraps_around():
    """방향키 이동은 양 끝에서 원형으로 순환해야 한다."""
    popup = UnitSuggestionPopup()
    popup.show_matches("k", QPoint(0, 0))
    count = popup.count()

    popup.move_selection(-1)  # 처음에서 위로 가면 마지막으로
    assert popup.currentRow() == count - 1

    popup.move_selection(1)  # 마지막에서 아래로 가면 처음으로
    assert popup.currentRow() == 0
    popup.close()


def test_selected_text_returns_current_item_text():
    popup = UnitSuggestionPopup()
    popup.show_matches("k", QPoint(0, 0))
    popup.setCurrentRow(0)
    assert popup.selected_text() == popup.item(0).text()
    popup.close()


# --- _TRAILING_UNIT_TOKEN: "200 k" 처럼 숫자 뒤 부분 단위만 완성 대상 ---


def test_trailing_unit_token_matches_number_then_partial_letters():
    match = _TRAILING_UNIT_TOKEN.search("F = 200 k")
    assert match is not None
    assert match.group(1) == "k"


def test_trailing_unit_token_does_not_match_plain_variable_name():
    """숫자 없이 시작하는 변수명("sigma")은 완성 대상으로 잡히면 안 된다."""
    match = _TRAILING_UNIT_TOKEN.search("sigma")
    assert match is None


def test_trailing_unit_token_matches_number_with_no_space():
    match = _TRAILING_UNIT_TOKEN.search("200k")
    assert match is not None
    assert match.group(1) == "k"


# --- _InlineTextEditor (실제 편집창) ---


def test_inline_editor_shows_suggestions_after_number_and_letter(window):
    """수식 편집창에 "200 k"까지 치면 단위 후보 팝업이 떠야 한다."""
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    editor: _InlineTextEditor = block._editor
    editor.setPlainText("F = 200 k")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    editor._update_suggestions()

    assert editor._suggestions.isVisible()
    editor._hide_suggestions()


def test_inline_editor_hides_suggestions_when_typing_plain_variable(window):
    """숫자 없이 변수명만 치면("sigma") 자동완성 팝업이 뜨면 안 된다."""
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    editor: _InlineTextEditor = block._editor
    editor.setPlainText("sigma")
    editor._update_suggestions()

    assert not editor._suggestions.isVisible()


def test_inline_editor_accepting_suggestion_replaces_only_partial_unit(window):
    """후보를 고르면 "k" 부분만 지워지고 골라둔 단위로 바뀌며, 나머지 수식은 그대로여야 한다."""
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    editor: _InlineTextEditor = block._editor
    editor.setPlainText("F = 200 k")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    editor._update_suggestions()
    assert editor._suggestions.isVisible()

    editor._suggestions.setCurrentRow(0)
    chosen = editor._suggestions.selected_text()
    editor._accept_suggestion()

    assert editor.toPlainText() == f"F = 200 {chosen}"
    assert not editor._suggestions.isVisible()


def test_inline_editor_enter_accepts_suggestion_instead_of_finishing_edit(window):
    """팝업이 떠 있을 때 Enter는 편집을 끝내지 않고 후보를 확정해야 한다."""
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    editor: _InlineTextEditor = block._editor
    editor.setPlainText("F = 200 k")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    editor._update_suggestions()
    assert editor._suggestions.isVisible()

    # QTest.keyClick()은 QWidget 대상이라 QGraphicsTextItem에는 못 쓴다 —
    # QKeyEvent를 직접 만들어 keyPressEvent()에 넘긴다.
    key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    editor.keyPressEvent(key_event)
    _app.processEvents()

    assert block._editor is not None  # 편집이 아직 안 끝났어야 함(팝업만 닫힘)
    assert not editor._suggestions.isVisible()
    assert editor.toPlainText().startswith("F = 200 ")

    editor2 = block._editor
    editor2.setPlainText("F = 200 kN")
    block.finish_editing()  # 테스트 정리(편집기 남겨두지 않음)


def _type_char_by_char(editor, text: str) -> None:
    """
    cursor.insertText()로 한 글자씩 넣어서 실제 타이핑과 같은 순서로 재현한다.

    Note:
        setPlainText()로 텍스트를 통째로 넣고 커서만 나중에 옮기면(다른
        테스트들처럼), contentsChanged가 "커서가 아직 맨 앞인 시점"에
        울려버려서 자동완성이 실제 타이핑과 다르게 동작할 수 있다 — 이
        헬퍼는 그런 시뮬레이션 오차 없이, 한 글자씩 넣을 때마다 커서가
        항상 방금 넣은 글자 뒤에 있는 "진짜 타이핑"과 동일하게 재현한다.
    """
    for ch in text:
        cursor = editor.textCursor()
        cursor.insertText(ch)
        editor.setTextCursor(cursor)


def test_inline_editor_end_to_end_typing_shows_and_accepts_suggestion(window):
    """
    한 글자씩 실제로 타이핑하듯 "F = 200 k"를 입력하면 팝업이 뜨고, 방향키로
    "kN"을 고른 뒤 Enter 두 번(확정 -> 편집 종료)으로 정상 계산까지 이어져야
    한다 — QTest로 실제 더블클릭까지 재현해서 확인한 시나리오.
    """
    from PySide6.QtTest import QTest

    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    editor: _InlineTextEditor = block._editor
    _type_char_by_char(editor, "F = 200 k")
    _app.processEvents()

    assert editor._suggestions.isVisible()
    assert "kN" in [editor._suggestions.item(i).text() for i in range(editor._suggestions.count())]

    down_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    editor.keyPressEvent(down_event)
    assert editor._suggestions.selected_text() == "kN"

    accept_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    editor.keyPressEvent(accept_event)
    assert editor.toPlainText() == "F = 200 kN"
    assert block._editor is editor  # 편집은 아직 끝나지 않아야 함(팝업만 확정)

    finish_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    editor.keyPressEvent(finish_event)
    _app.processEvents()

    assert block._editor is None
    assert block.input_text() == "F = 200 kN"
    result = block.result()
    assert result is not None and not result.is_error
    assert float(result.value.magnitude) == 200.0
    assert str(result.value.units) == "kilonewton"


def test_inline_editor_escape_hides_popup_without_ending_edit(window):
    """Esc는 팝업만 닫고, 편집 중이던 내용은 그대로 두고 편집도 계속 유지되어야 한다."""
    block = MathBlock(position=(0, 0))
    window._scene.addItem(block)
    block.start_editing()
    _app.processEvents()

    editor: _InlineTextEditor = block._editor
    _type_char_by_char(editor, "F = 200 k")
    assert editor._suggestions.isVisible()

    esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    editor.keyPressEvent(esc_event)

    assert not editor._suggestions.isVisible()
    assert block._editor is editor  # 편집은 계속 유지되어야 함
    assert editor.toPlainText() == "F = 200 k"  # 내용은 그대로


# --- _UnitEditor: 필드 전체가 단위 하나 ---


def test_unit_editor_shows_suggestions_for_whole_field(window):
    """단위 편집창(Ctrl+더블클릭)은 입력된 전체를 완성 대상으로 삼아야 한다."""
    scope = Scope()
    block = MathBlock(position=(0, 0))
    block.set_input_text("F = 200 kN")
    block.evaluate(scope)
    window._scene.addItem(block)
    block.start_unit_editing()
    _app.processEvents()

    editor: _UnitEditor = block._unit_editor
    editor.setPlainText("k")
    editor._update_suggestions()

    assert editor._suggestions.isVisible()
    editor._hide_suggestions()


def test_unit_editor_accepting_suggestion_replaces_whole_text(window):
    """단위 편집창에서 후보를 고르면 필드 전체가 그 단위로 바뀌어야 한다."""
    scope = Scope()
    block = MathBlock(position=(0, 0))
    block.set_input_text("F = 200 kN")
    block.evaluate(scope)
    window._scene.addItem(block)
    block.start_unit_editing()
    _app.processEvents()

    editor: _UnitEditor = block._unit_editor
    editor.setPlainText("M")
    editor._update_suggestions()
    assert editor._suggestions.isVisible()

    editor._suggestions.setCurrentRow(0)
    chosen = editor._suggestions.selected_text()
    editor._accept_suggestion()

    assert editor.toPlainText() == chosen
    block.finish_unit_editing()
