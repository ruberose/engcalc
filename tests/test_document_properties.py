"""
문서 속성(제목/작성자, 머리글·바닥글 표시 여부) 기능 검증.

사용자 요청: "문서 속성(제목/작성자) 편집 대화상자... PDF 출력물이 훨씬
'문서'다워집니다" — 메뉴 > 파일 > 문서 속성...에서 제목/작성자를 정하면
파일에 저장되고, PDF 내보내기/인쇄 머리글에 반영되는지 확인한다.
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication

import app.main_window as main_window_module
from app.main_window import MainWindow
from file_io.file_manager import load_document
from ui.document_properties_dialog import DocumentPropertiesDialog

_app = QApplication.instance() or QApplication([])


# --- DocumentPropertiesDialog (위젯 단위) ---


def test_dialog_prefills_current_values():
    dialog = DocumentPropertiesDialog(title="응력 검토", author="홍길동", show_header_footer=True)
    assert dialog.result_properties() == ("응력 검토", "홍길동", True)
    dialog.close()


def test_dialog_defaults_when_nothing_set():
    dialog = DocumentPropertiesDialog()
    assert dialog.result_properties() == ("", "", False)
    dialog.close()


def test_dialog_strips_whitespace_from_title_and_author():
    dialog = DocumentPropertiesDialog()
    dialog._title_input.setText("  제목  ")
    dialog._author_input.setText("  이름  ")
    assert dialog.result_properties() == ("제목", "이름", False)
    dialog.close()


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


def test_display_title_falls_back_to_filename_when_not_set(window):
    assert window._document_title == ""
    assert window._document_display_title() == main_window_module._DEFAULT_TITLE

    window._current_file_path = "/tmp/응력검토.engcalc"
    assert window._document_display_title() == "응력검토"


def test_display_title_prefers_custom_title_over_filename(window):
    window._current_file_path = "/tmp/calc1.engcalc"
    window._document_title = "2층 보 설계"

    assert window._document_display_title() == "2층 보 설계"


def test_accepting_properties_dialog_applies_values_and_marks_modified(window, monkeypatch):
    def fake_exec(self):
        self._title_input.setText("응력 검토")
        self._author_input.setText("홍길동")
        self._show_header_footer_checkbox.setChecked(True)
        return DocumentPropertiesDialog.DialogCode.Accepted

    monkeypatch.setattr(DocumentPropertiesDialog, "exec", fake_exec)
    assert not window._is_modified

    window._on_document_properties()

    assert window._document_title == "응력 검토"
    assert window._document_author == "홍길동"
    assert window._show_header_footer is True
    assert window._is_modified


def test_cancelling_properties_dialog_keeps_current_values(window, monkeypatch):
    window._document_title = "기존 제목"
    window._is_modified = False

    monkeypatch.setattr(DocumentPropertiesDialog, "exec", lambda self: DocumentPropertiesDialog.DialogCode.Rejected)

    window._on_document_properties()

    assert window._document_title == "기존 제목"
    assert not window._is_modified


def test_accepting_with_unchanged_values_does_not_mark_modified(window, monkeypatch):
    """값이 실제로 안 바뀌었으면 굳이 "수정됨" 표시를 켤 필요 없다."""
    monkeypatch.setattr(DocumentPropertiesDialog, "exec", lambda self: DocumentPropertiesDialog.DialogCode.Accepted)
    assert not window._is_modified

    window._on_document_properties()  # 기본값 그대로 확인만 누른 상황

    assert not window._is_modified


def test_new_document_resets_properties(window, monkeypatch):
    from ui.new_document_dialog import NewDocumentDialog

    window._document_title = "이전 문서 제목"
    window._document_author = "이전 작성자"
    window._show_header_footer = True

    monkeypatch.setattr(NewDocumentDialog, "exec", lambda self: NewDocumentDialog.DialogCode.Accepted)
    window._on_new_document()

    assert window._document_title == ""
    assert window._document_author == ""
    assert window._show_header_footer is False


def test_save_then_load_round_trips_document_properties(window, tmp_path):
    window._document_title = "응력 검토"
    window._document_author = "홍길동"
    window._show_header_footer = True
    file_path = str(tmp_path / "doc.engcalc")

    assert window._save_to_path(file_path)

    saved = load_document(file_path)
    assert saved["metadata"]["title"] == "응력 검토"
    assert saved["metadata"]["author"] == "홍길동"
    assert saved["metadata"]["show_header_footer"] is True

    window._document_title = ""
    window._document_author = ""
    window._show_header_footer = False
    window._load_from_path(file_path)

    assert window._document_title == "응력 검토"
    assert window._document_author == "홍길동"
    assert window._show_header_footer is True


def test_loading_old_file_without_properties_fields_defaults_to_empty(window, tmp_path):
    """제목/작성자/머리글 필드가 없는 옛 파일(하위 호환)은 빈 값으로 열려야 한다."""
    file_path = tmp_path / "old.engcalc"
    file_path.write_text('{"version": "1.0", "metadata": {}, "blocks": []}', encoding="utf-8")

    window._document_title = "이전 값"
    window._load_from_path(str(file_path))

    assert window._document_title == ""
    assert window._document_author == ""
    assert window._show_header_footer is False


def test_export_pdf_passes_document_properties_to_export_function(window, monkeypatch):
    from blocks.math_block import MathBlock
    from PySide6.QtWidgets import QFileDialog

    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    window._document_title = "응력 검토"
    window._document_author = "홍길동"
    window._show_header_footer = True

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: ("/tmp/out.pdf", ""))
    calls = []
    monkeypatch.setattr(
        main_window_module, "export_to_pdf", lambda *a, **kw: calls.append(kw) or True
    )

    window._on_export_pdf()

    assert len(calls) == 1
    assert calls[0]["title"] == "응력 검토"
    assert calls[0]["author"] == "홍길동"
    assert calls[0]["show_header_footer"] is True


def test_print_passes_document_properties_to_print_function(window, monkeypatch):
    from blocks.math_block import MathBlock
    from PySide6.QtPrintSupport import QPrintDialog

    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    window._scene.addItem(block)
    window._document_title = "응력 검토"
    window._document_author = "홍길동"
    window._show_header_footer = True

    monkeypatch.setattr(QPrintDialog, "exec", lambda self: QPrintDialog.DialogCode.Accepted)
    calls = []
    monkeypatch.setattr(main_window_module, "print_scene", lambda *a, **kw: calls.append(kw) or True)

    window._on_print()

    assert len(calls) == 1
    assert calls[0]["title"] == "응력 검토"
    assert calls[0]["author"] == "홍길동"
    assert calls[0]["show_header_footer"] is True
