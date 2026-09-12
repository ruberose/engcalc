"""
격자 보기 켜기/끄기(메뉴 > 보기 > 격자 보기) 기능 검증.

사용자 요청: "격자 보기 켜기/끄기" — 화면 깔끔하게 보고 싶을 때 끌 수 있게.
앱을 껐다 켜도 마지막으로 고른 상태가 유지된다(app/settings.py에 저장).

부수적으로 고친 버그: PDF/PNG 내보내기·인쇄는 내보내는 동안만 격자를 잠깐
끄는데, 끝나고 항상 "다시 켬(True)"으로 고정 복원하고 있었다 — 사용자가
격자를 꺼둔 상태로 내보내기를 하면, 끝난 뒤 화면에 격자가 도로 켜지는
버그였다. 내보내기 전 상태를 기억해뒀다가 그 상태로 복원하도록 고쳤다.

tests/conftest.py의 autouse fixture(isolated_qsettings)가 QSettings를
테스트 전용 임시 파일로 돌려두므로, 실제 사용자 설정은 건드리지 않는다.
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PySide6.QtPrintSupport import QPrintDialog

import app.main_window as main_window_module
from app.main_window import MainWindow
from app.settings import get_grid_visible, set_grid_visible
from blocks.math_block import MathBlock
from canvas.document_scene import DocumentScene

_app = QApplication.instance() or QApplication([])


# --- app/settings.py ---


def test_grid_visible_defaults_to_true():
    assert get_grid_visible() is True


def test_set_grid_visible_persists():
    set_grid_visible(False)
    assert get_grid_visible() is False
    set_grid_visible(True)
    assert get_grid_visible() is True


# --- DocumentScene ---


def test_scene_is_grid_visible_matches_set_grid_visible():
    scene = DocumentScene()
    assert scene.is_grid_visible() is True
    scene.set_grid_visible(False)
    assert scene.is_grid_visible() is False


# --- MainWindow 연동 ---


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


def test_new_window_applies_saved_grid_preference(monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings

    ini_path = str(tmp_path / "custom_settings.ini")
    monkeypatch.setattr("app.settings._settings", lambda: QSettings(ini_path, QSettings.Format.IniFormat))
    set_grid_visible(False)

    win = MainWindow()
    try:
        assert win._scene.is_grid_visible() is False
        assert not win._grid_visible_action.isChecked()
    finally:
        win._scene.selectionChanged.disconnect(win._on_selection_changed)
        win._scene.changed.disconnect(win._on_scene_changed)
        win._autosave_timer.stop()
        win.close()
        _app.processEvents()
        del win
        gc.collect()
        _app.processEvents()


def test_toggling_action_updates_scene_and_saves_preference(window):
    assert window._grid_visible_action.isChecked()
    assert window._scene.is_grid_visible()

    window._grid_visible_action.setChecked(False)

    assert not window._scene.is_grid_visible()
    assert get_grid_visible() is False


def test_export_pdf_restores_grid_off_preference_instead_of_forcing_on(window, monkeypatch, tmp_path):
    """격자를 꺼둔 상태로 PDF를 내보내면, 끝난 뒤에도 꺼진 채로 남아야 한다(강제로 켜지면 버그)."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    window._grid_visible_action.setChecked(False)
    assert not window._scene.is_grid_visible()

    out_path = str(tmp_path / "out.pdf")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (out_path, ""))
    monkeypatch.setattr(main_window_module, "export_to_pdf", lambda *a, **kw: True)

    window._on_export_pdf()

    assert not window._scene.is_grid_visible()


def test_export_pdf_restores_grid_on_when_it_was_on(window, monkeypatch, tmp_path):
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    assert window._scene.is_grid_visible()

    out_path = str(tmp_path / "out.pdf")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (out_path, ""))
    monkeypatch.setattr(main_window_module, "export_to_pdf", lambda *a, **kw: True)

    window._on_export_pdf()

    assert window._scene.is_grid_visible()


def test_export_png_restores_grid_off_preference(window, monkeypatch, tmp_path):
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    window._grid_visible_action.setChecked(False)

    out_path = str(tmp_path / "out.png")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (out_path, ""))
    monkeypatch.setattr(main_window_module, "export_to_png", lambda *a, **kw: True)

    window._on_export_png()

    assert not window._scene.is_grid_visible()


def test_print_restores_grid_off_preference(window, monkeypatch):
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    window._grid_visible_action.setChecked(False)

    monkeypatch.setattr(QPrintDialog, "exec", lambda self: QPrintDialog.DialogCode.Accepted)
    monkeypatch.setattr(main_window_module, "print_scene", lambda *a, **kw: True)

    window._on_print()

    assert not window._scene.is_grid_visible()
