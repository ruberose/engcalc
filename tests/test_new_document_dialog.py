"""ui/new_document_dialog.py — 새 문서 형식 선택 대화상자 테스트."""

from PySide6.QtWidgets import QApplication

from canvas.document_scene import PAPER_SIZES_MM
from ui.new_document_dialog import NewDocumentDialog

_app = QApplication.instance() or QApplication([])


def test_default_selection_is_freeform_with_size_combo_disabled():
    dialog = NewDocumentDialog()
    assert dialog.result_format() == ("freeform", "A4")
    assert not dialog._paper_size_combo.isEnabled()
    dialog.close()


def test_selecting_paper_enables_size_combo_and_changes_result():
    dialog = NewDocumentDialog()
    dialog._paper_radio.setChecked(True)

    assert dialog._paper_size_combo.isEnabled()
    document_format, paper_size = dialog.result_format()
    assert document_format == "paper"
    assert paper_size in PAPER_SIZES_MM
    dialog.close()


def test_switching_back_to_freeform_disables_size_combo_again():
    dialog = NewDocumentDialog()
    dialog._paper_radio.setChecked(True)
    dialog._freeform_radio.setChecked(True)

    assert not dialog._paper_size_combo.isEnabled()
    assert dialog.result_format() == ("freeform", "A4")
    dialog.close()


def test_paper_size_combo_lists_all_known_paper_sizes():
    dialog = NewDocumentDialog()
    items = [dialog._paper_size_combo.itemText(i) for i in range(dialog._paper_size_combo.count())]
    assert set(items) == set(PAPER_SIZES_MM.keys())
    dialog.close()
