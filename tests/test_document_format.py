"""
"새로 만들기" 시 문서 형식(자유 캔버스 / A4 용지) 선택과 저장/불러오기 연동 검증.

사용자 요청: "새 파일을 만들 때 형식을 고정하는게 좋을 것 같은데 어때?" —
NewDocumentDialog에서 고른 형식이 DocumentScene에 반영되고, 저장 시 파일
메타데이터에 담겨 다시 열어도 그대로 유지되는지 확인한다.
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from blocks.math_block import MathBlock
from file_io.file_manager import load_document
from ui.new_document_dialog import NewDocumentDialog

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


def test_new_document_applies_chosen_paper_format(window, monkeypatch):
    """"새로 만들기"에서 "문서(용지 기반)"를 고르면 씬에 그대로 반영돼야 한다."""

    def fake_exec(self):
        self._paper_radio.setChecked(True)
        return NewDocumentDialog.DialogCode.Accepted

    monkeypatch.setattr(NewDocumentDialog, "exec", fake_exec)

    window._on_new_document()

    assert window._scene.document_format() == "paper"
    assert window._scene.paper_size() == "A4"


def test_new_document_keeps_freeform_when_dialog_default_accepted(window, monkeypatch):
    """대화상자에서 기본값(자유 캔버스) 그대로 확인을 누르면 지금까지와 동일해야 한다."""
    monkeypatch.setattr(NewDocumentDialog, "exec", lambda self: NewDocumentDialog.DialogCode.Accepted)

    window._on_new_document()

    assert window._scene.document_format() == "freeform"


def test_cancelling_new_document_dialog_keeps_current_document(window, monkeypatch):
    """형식 선택 대화상자에서 취소하면 지금 문서(형식·내용)를 그대로 둬야 한다."""
    window._scene.set_document_format("paper", "A4")
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)

    monkeypatch.setattr(NewDocumentDialog, "exec", lambda self: NewDocumentDialog.DialogCode.Rejected)

    window._on_new_document()

    assert window._scene.document_format() == "paper"
    assert any(isinstance(item, MathBlock) for item in window._scene.items())


def test_save_then_load_round_trips_document_format(window, tmp_path):
    """"paper"/"A4"로 저장한 문서를 다시 열면 형식이 그대로 유지돼야 한다."""
    window._scene.set_document_format("paper", "A4")
    file_path = str(tmp_path / "doc.engcalc")

    assert window._save_to_path(file_path)

    saved = load_document(file_path)
    assert saved["metadata"]["document_format"] == "paper"
    assert saved["metadata"]["paper_size"] == "A4"

    window._scene.set_document_format("freeform")  # 저장된 값과 다르게 흩트려놓고 다시 불러오기로 확인
    window._load_from_path(file_path)

    assert window._scene.document_format() == "paper"
    assert window._scene.paper_size() == "A4"


def test_loading_old_file_without_format_field_defaults_to_freeform(window, tmp_path):
    """형식 필드가 없는 옛 파일(하위 호환)은 자유 캔버스로 열려야 한다."""
    file_path = tmp_path / "old.engcalc"
    file_path.write_text('{"version": "1.0", "metadata": {"title": "old"}, "blocks": []}', encoding="utf-8")

    window._scene.set_document_format("paper", "A4")
    window._load_from_path(str(file_path))

    assert window._scene.document_format() == "freeform"


def test_autosave_writes_document_format(window):
    """자동 저장 파일에도 문서 형식이 함께 기록돼야 한다(복구 시 형식도 같이 복원되도록)."""
    window._scene.set_document_format("paper", "A4")
    window._write_autosave()

    import app.main_window as main_window_module

    # tests/conftest.py의 autouse fixture가 app.main_window.autosave_file_path를
    # 이 테스트 전용 임시 경로로 돌려뒀으므로, 실제 자동 저장 파일이 쓰인 그 경로를
    # 똑같이 통해서 읽어야 한다(app.settings의 원본 함수를 다시 부르면 안 됨).
    saved = load_document(main_window_module.autosave_file_path())
    assert saved["metadata"]["document_format"] == "paper"
    assert saved["metadata"]["paper_size"] == "A4"
