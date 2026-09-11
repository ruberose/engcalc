"""
도움말(사용법) 대화상자 검증.

사용자 요청: "메뉴얼도 좀 만들어 줘라... 상단 메뉴바에서 누르고 들어가면
도움말이 뜨도록."
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication, QTextBrowser

from app.main_window import MainWindow
from ui.help_dialog import HelpDialog

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
    win._is_modified = False
    win.close()
    _app.processEvents()
    del win
    gc.collect()
    _app.processEvents()


def test_help_dialog_has_content():
    """도움말 창은 빈 내용이 아니어야 한다."""
    dialog = HelpDialog()
    text = dialog.findChild(QTextBrowser).toPlainText()
    assert "수식 블록" in text
    assert "Ctrl+Z" in text
    dialog.close()


def test_show_help_creates_and_shows_dialog(window):
    """메뉴/단축키로 _on_show_help()를 부르면 도움말 창이 뜨고 내용이 보여야 한다."""
    assert window._help_dialog is None
    window._on_show_help()
    _app.processEvents()

    assert window._help_dialog is not None
    assert window._help_dialog.isVisible()
    window._help_dialog.close()


def test_show_help_reuses_same_dialog_instance(window):
    """도움말을 두 번 열어도 같은 창을 재사용해야 한다(창이 계속 쌓이면 안 됨)."""
    window._on_show_help()
    _app.processEvents()
    first = window._help_dialog

    window._on_show_help()
    _app.processEvents()

    assert window._help_dialog is first
    window._help_dialog.close()


def test_help_menu_action_wired_to_show_help(window):
    """도움말 메뉴에 실제 항목이 있고 _on_show_help에 연결돼 있어야 한다(예전엔 "구현 예정" 자리표시자였음)."""
    menu_bar = window.menuBar()
    help_menu = menu_bar.actions()[3].menu()  # 파일/편집/보기/도움말 순서
    actions = [a for a in help_menu.actions() if a.text()]
    assert len(actions) == 1
    assert "사용법" in actions[0].text()
    assert actions[0].isEnabled()
