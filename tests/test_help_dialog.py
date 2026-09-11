"""
도움말(사용법) 대화상자 검증.

사용자 요청:
- "메뉴얼도 좀 만들어 줘라... 상단 메뉴바에서 누르고 들어가면 도움말이 뜨도록."
- "도움말에 두가지 페이지를 만들어서 1. 기본 사용법, 2. 이 프로그램에서
  적용되는 수식작성법"
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication, QTabWidget, QTextBrowser

from app.main_window import MainWindow
from ui.help_dialog import HelpDialog

_app = QApplication.instance() or QApplication([])


def _all_pages_text(dialog: HelpDialog) -> str:
    """도움말 창의 모든 탭(페이지) 내용을 하나로 합쳐서 반환한다 (검색용)."""
    return "\n".join(browser.toPlainText() for browser in dialog.findChildren(QTextBrowser))


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


def test_help_dialog_has_two_tabs():
    """도움말은 "기본 사용법"/"수식 작성법" 두 페이지(탭)로 나뉘어 있어야 한다."""
    dialog = HelpDialog()
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() == 2
    titles = [tabs.tabText(i) for i in range(tabs.count())]
    assert "기본 사용법" in titles
    assert "수식 작성법" in titles
    dialog.close()


def test_basic_usage_tab_has_content():
    """"기본 사용법" 탭은 블록 조작/단축키 내용을 담고 있어야 한다."""
    dialog = HelpDialog()
    tabs = dialog.findChild(QTabWidget)
    basic_text = tabs.widget(0).toPlainText()
    assert "더블클릭" in basic_text
    assert "Ctrl+Z" in basic_text
    dialog.close()


def test_formula_syntax_tab_has_content():
    """"수식 작성법" 탭은 연산자/함수/첨자 문법 내용을 담고 있어야 한다."""
    dialog = HelpDialog()
    tabs = dialog.findChild(QTabWidget)
    formula_text = tabs.widget(1).toPlainText()
    assert "아래첨자" in formula_text
    assert "F_y" in formula_text
    dialog.close()


def test_help_dialog_documents_calculation_level():
    """
    사용자 요청: "어느 수준까지 되는지 나한테 알려주고, 도움말에도 추가해줘"

    diff(x^2, x)식 "기호식" 계산은 안 되고, limit/solve/integrate(정적분)/Sum
    처럼 결과가 숫자로 떨어지는 고급 계산은 된다는 걸 실제로 evaluate()로
    확인했으므로(engine/evaluator.py), 그 사실이 도움말에도 반영되어 있는지
    확인한다.
    """
    dialog = HelpDialog()
    text = _all_pages_text(dialog)
    assert "SymPy" in text
    assert "limit" in text
    assert "integrate" in text
    assert "diff" in text
    assert "기호식" in text  # 안 되는 것에 대한 설명이 있어야 함
    dialog.close()


def test_help_dialog_documents_latex_not_supported():
    """
    사용자 요청: "라텍스 문법은 아예 고려하지 말고 사용하자. 헷갈리지 않도록
    아예 없애버리는게 낫겠어."

    LaTeX 문법이 지원되지 않는다는 사실과, 그 대신 무엇을 써야 하는지(예:
    sqrt(x))가 도움말에 안내되어 있는지 확인한다.
    """
    dialog = HelpDialog()
    text = _all_pages_text(dialog)
    assert "LaTeX" in text
    assert "지원하지 않" in text
    assert "sqrt(x)" in text
    dialog.close()


def test_formula_syntax_tab_documents_correct_subscript_rule():
    """
    이전엔 "sigma_{allow}"처럼 중괄호로 여러 글자를 묶는 수식 블록 첨자가
    된다고 잘못 안내했었다(실제로는 계산이 안 됨 — LaTeX 취급되어 거부됨).
    지금은 "한 글자만 자동 첨자, 중괄호 묶음은 지원 안 함"이 정확히
    안내되어야 한다.
    """
    dialog = HelpDialog()
    tabs = dialog.findChild(QTabWidget)
    formula_text = tabs.widget(1).toPlainText()
    assert "sigma_{allow}" not in formula_text  # 잘못된 예시가 남아있으면 안 됨
    assert "지원하지 않습니다" in formula_text
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
