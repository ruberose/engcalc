"""
메뉴 > 파일 > PNG로 내보내기 기능(main_window 배선) 검증.

file_io/image_exporter.py의 실제 렌더링/파일 생성 로직은
tests/test_image_exporter.py에서 이미 검증하므로, 여기서는 "메뉴를 눌렀을 때
main_window가 파일 선택 대화상자·export_to_png를 올바르게 부르는지"에 집중한다
(app/main_window.py의 _on_export_pdf 배선 방식을 그대로 따랐다).
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

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


def test_export_png_menu_action_exists(window):
    file_menu = window.menuBar().actions()[0].menu()  # 파일/편집/보기/도움말 순서
    labels = [a.text() for a in file_menu.actions()]
    assert any("PNG로 내보내기" in label for label in labels)


def test_cancelling_file_dialog_does_not_export(window, monkeypatch):
    """파일 선택 대화상자에서 취소하면 export_to_png를 아예 부르면 안 된다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: ("", ""))
    calls = []
    monkeypatch.setattr(main_window_module, "export_to_png", lambda *a, **kw: calls.append(1) or True)

    window._on_export_png()

    assert calls == []


def test_export_png_appends_extension_and_calls_exporter(window, monkeypatch, tmp_path):
    """확장자 없이 경로를 골라도 .png가 붙고, export_to_png가 그 경로로 호출돼야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)

    chosen_path = str(tmp_path / "출력")  # 확장자 없이
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (chosen_path, ""))

    calls = []
    monkeypatch.setattr(main_window_module, "export_to_png", lambda scene, path: calls.append(path) or True)

    window._on_export_png()

    assert len(calls) == 1
    assert calls[0] == chosen_path + ".png"


def test_export_png_with_empty_canvas_shows_message(window, monkeypatch, tmp_path):
    """캔버스가 비어 있어서 export_to_png가 False를 돌려주면 안내 메시지가 떠야 한다."""
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(tmp_path / "out.png"), ""))
    monkeypatch.setattr(main_window_module, "export_to_png", lambda *a, **kw: False)

    informed = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: informed.append(1))

    window._on_export_png()

    assert informed == [1]


def test_export_png_clears_selection_and_restores_grid_visibility(window, monkeypatch, tmp_path):
    """PDF 내보내기와 같은 관례: 내보내는 동안 선택 해제 + 격자를 끄고, 끝나면 다시 켠다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    block.setSelected(True)

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(tmp_path / "out.png"), ""))

    grid_visible_during_export = []

    def fake_export_to_png(scene, path):
        grid_visible_during_export.append(scene._grid_visible)
        return True

    monkeypatch.setattr(main_window_module, "export_to_png", fake_export_to_png)

    window._on_export_png()

    assert grid_visible_during_export == [False]
    assert window._scene._grid_visible is True
    assert not block.isSelected()


def test_export_png_success_shows_status_message(window, monkeypatch, tmp_path):
    out_path = str(tmp_path / "out.png")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (out_path, ""))
    monkeypatch.setattr(main_window_module, "export_to_png", lambda *a, **kw: True)

    window._on_export_png()

    assert out_path in window.statusBar().currentMessage()
