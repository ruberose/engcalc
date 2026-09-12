"""
메뉴 > 파일 > 인쇄(Ctrl+P) 기능 검증.

실제 인쇄 대화상자(QPrintDialog)는 OS 네이티브 모달이라 테스트에서 그대로
띄울 수 없으므로, QPrintDialog.exec()과 file_io.pdf_exporter.print_scene을
monkeypatch로 대체해서 "사용자가 확인/취소를 눌렀을 때 main_window가 올바른
값으로 print_scene을 부르는지/안 부르는지"만 검증한다. print_scene() 자체의
동작(페이지 렌더링)은 tests/test_pdf_exporter.py에서 이미 검증한다.
"""

import gc

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtPrintSupport import QPrintDialog
from PySide6.QtWidgets import QApplication, QMessageBox

import app.main_window as main_window_module
from app.main_window import MainWindow
from blocks.math_block import MathBlock

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


def test_print_menu_action_uses_standard_shortcut(window):
    """인쇄 메뉴 항목은 플랫폼 표준 단축키(Ctrl+P)를 써야 한다."""
    file_menu = window.menuBar().actions()[0].menu()  # 파일/편집/보기/도움말 순서
    print_actions = [a for a in file_menu.actions() if "인쇄" in a.text()]
    assert len(print_actions) == 1
    assert print_actions[0].shortcut() == QKeySequence.StandardKey.Print


def test_print_with_empty_canvas_shows_message_and_skips_dialog(window, monkeypatch):
    """빈 캔버스에서는 인쇄 대화상자조차 띄우지 않고 안내만 해야 한다."""
    dialog_shown = []
    monkeypatch.setattr(QPrintDialog, "exec", lambda self: dialog_shown.append(True) or QPrintDialog.DialogCode.Accepted)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: None)

    window._on_print()

    assert dialog_shown == []


def test_accepting_print_dialog_calls_print_scene_with_title(window, monkeypatch):
    """대화상자에서 확인을 누르면 현재 문서 제목으로 print_scene이 호출돼야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)

    monkeypatch.setattr(QPrintDialog, "exec", lambda self: QPrintDialog.DialogCode.Accepted)

    calls = []
    monkeypatch.setattr(
        main_window_module, "print_scene", lambda scene, printer, title="": calls.append((scene, title)) or True
    )

    window._on_print()

    assert len(calls) == 1
    printed_scene, printed_title = calls[0]
    assert printed_scene is window._scene
    assert printed_title == main_window_module._DEFAULT_TITLE


def test_cancelling_print_dialog_does_not_print(window, monkeypatch):
    """대화상자에서 취소를 누르면 print_scene을 아예 부르면 안 된다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)

    monkeypatch.setattr(QPrintDialog, "exec", lambda self: QPrintDialog.DialogCode.Rejected)

    calls = []
    monkeypatch.setattr(main_window_module, "print_scene", lambda *a, **kw: calls.append(1) or True)

    window._on_print()

    assert calls == []


def test_print_clears_selection_and_restores_grid_visibility(window, monkeypatch):
    """인쇄 중에는 선택 해제 + 격자를 꺼두고, 끝나면 다시 켜야 한다(PDF 내보내기와 동일한 관례)."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    block.setSelected(True)

    monkeypatch.setattr(QPrintDialog, "exec", lambda self: QPrintDialog.DialogCode.Accepted)

    grid_visible_during_print = []

    def fake_print_scene(scene, printer, title=""):
        grid_visible_during_print.append(scene._grid_visible)
        return True

    monkeypatch.setattr(main_window_module, "print_scene", fake_print_scene)

    window._on_print()

    assert grid_visible_during_print == [False]
    assert window._scene._grid_visible is True
    assert not block.isSelected()
