"""
자동 저장 / 비정상 종료 복구 기능 검증.

사용자 요청: "제일 먼저 만들어야 하는 자동저장기능을 만들어보자"

설계:
    - 저장 안 한 변경사항이 있을 때만(주기적으로) 별도의 자동 저장 파일에 써둔다
      (app/settings.py의 autosave_file_path()가 가리키는, 사용자가 실제로
      저장하는 .engcalc 파일과는 별개인 위치).
    - 정상적으로 저장/새 문서/파일 열기/종료를 하면 이 파일을 지운다.
    - 그래서 다음 실행 때 이 파일이 남아있다는 것 자체가 "지난번에 비정상
      종료됐다"는 신호이고, 그때만 복구할지 물어본다.

tests/conftest.py의 autouse fixture가 모든 테스트에서 자동 저장 경로를
tmp_path 아래로 돌려두므로, 실제 사용자의 ~/.engcalc/autosave.engcalc 파일은
전혀 건드리지 않는다.
"""

import gc
import json

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow
from blocks.math_block import MathBlock
from file_io.file_manager import save_document
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


def _math_blocks(win: MainWindow) -> list[MathBlock]:
    return [i for i in win._scene.items() if isinstance(i, MathBlock)]


def _add_math_block(win: MainWindow, text: str) -> MathBlock:
    block = MathBlock(position=(0, 0))
    block.set_input_text(text)
    win._scene.addItem(block)
    win._scene.recalculate_all()
    return block


# --- 자동 저장 쓰기/지우기 ---


def test_autosave_tick_does_nothing_without_changes(window, tmp_path):
    """저장 안 한 변경사항이 없으면 자동 저장 파일을 만들지 않아야 한다."""
    autosave_path = tmp_path / "autosave.engcalc"
    window._is_modified = False
    window._on_autosave_tick()
    assert not autosave_path.exists()


def test_autosave_tick_writes_when_modified(window, tmp_path):
    """저장 안 한 변경사항이 있으면 자동 저장 파일이 만들어져야 한다."""
    _add_math_block(window, "a = 100")
    window._is_modified = True

    autosave_path = tmp_path / "autosave.engcalc"
    window._on_autosave_tick()

    assert autosave_path.exists()
    data = json.loads(autosave_path.read_text(encoding="utf-8"))
    assert len(data["blocks"]) == 1
    assert data["blocks"][0]["expression"] == "a = 100"


def test_write_autosave_includes_original_file_path(window, tmp_path):
    """자동 저장 파일엔 나중에 복구할 때 쓸 원본 파일 경로도 같이 적혀야 한다."""
    window._current_file_path = r"C:\docs\실무계산서.engcalc"
    window._is_modified = True
    window._write_autosave()

    autosave_path = tmp_path / "autosave.engcalc"
    data = json.loads(autosave_path.read_text(encoding="utf-8"))
    assert data["metadata"]["original_file_path"] == r"C:\docs\실무계산서.engcalc"


def test_clear_autosave_removes_file(window, tmp_path):
    """_clear_autosave()는 자동 저장 파일을 지우고 복구 플래그도 정리해야 한다."""
    window._is_modified = True
    window._write_autosave()
    autosave_path = tmp_path / "autosave.engcalc"
    assert autosave_path.exists()

    window._recovered_from_autosave = True
    window._clear_autosave()

    assert not autosave_path.exists()
    assert window._recovered_from_autosave is False


def test_clear_autosave_is_safe_when_no_file_exists(window):
    """자동 저장 파일이 애초에 없어도 _clear_autosave()가 에러 없이 넘어가야 한다."""
    window._clear_autosave()  # 예외를 던지면 이 테스트가 바로 실패함


def test_saving_document_clears_autosave(window, tmp_path):
    """진짜 파일로 저장하면 자동 저장 파일은 더 이상 필요 없으므로 지워져야 한다."""
    _add_math_block(window, "a = 1")
    window._is_modified = True
    window._write_autosave()
    autosave_path = tmp_path / "autosave.engcalc"
    assert autosave_path.exists()

    real_file = tmp_path / "real.engcalc"
    window._save_to_path(str(real_file))

    assert not autosave_path.exists()
    assert real_file.exists()


def test_new_document_clears_autosave(window, tmp_path, monkeypatch):
    """"새로 만들기"를 하면 이전 문서의 자동 저장 내용은 지워져야 한다."""
    window._is_modified = True
    window._write_autosave()
    autosave_path = tmp_path / "autosave.engcalc"
    assert autosave_path.exists()

    # _on_new_document()는 _is_modified=True일 때 "저장 안 한 변경사항이
    # 있습니다" 확인창을 먼저 띄우고, 그다음 문서 형식(자유 캔버스/A4 용지)을
    # 고르는 대화상자도 띄운다(둘 다 자동 저장과는 별개의 기존/신규 동작) —
    # 자동 테스트에서 실제 대화상자가 뜨면 영원히 멈추므로 각각 "버리기"/
    # "기본값(자유 캔버스)으로 확인"을 선택한 것으로 흉내낸다.
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(NewDocumentDialog, "exec", lambda self: NewDocumentDialog.DialogCode.Accepted)

    window._on_new_document()

    assert not autosave_path.exists()


# --- 시작할 때 복구 ---


def test_no_autosave_file_means_no_recovery_prompt(monkeypatch, tmp_path):
    """자동 저장 파일이 없으면 복구를 물어보지 않고 조용히 지나가야 한다."""
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: asked.append(1) or QMessageBox.StandardButton.Yes)

    win = MainWindow()
    win.show()
    _app.processEvents()

    assert asked == []
    assert win._is_modified is False

    win._scene.selectionChanged.disconnect(win._on_selection_changed)
    win._scene.changed.disconnect(win._on_scene_changed)
    win._autosave_timer.stop()
    win._is_modified = False
    win.close()
    _app.processEvents()
    gc.collect()


def test_corrupted_autosave_file_is_silently_discarded(monkeypatch, tmp_path):
    """자동 저장 파일이 깨져 있으면(JSON 아님) 에러 없이 조용히 지우고 새 문서로 시작해야 한다."""
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: asked.append(1) or QMessageBox.StandardButton.Yes)

    autosave_path = tmp_path / "autosave.engcalc"
    autosave_path.write_text("이건 JSON이 아님{{{", encoding="utf-8")

    win = MainWindow()  # 예외를 던지면 이 테스트가 바로 실패함
    win.show()
    _app.processEvents()

    assert asked == []  # 깨진 파일이면 물어보지도 않고 그냥 버림
    assert not autosave_path.exists()
    assert win._scene.to_blocks_list() == []

    win._scene.selectionChanged.disconnect(win._on_selection_changed)
    win._scene.changed.disconnect(win._on_scene_changed)
    win._autosave_timer.stop()
    win._is_modified = False
    win.close()
    _app.processEvents()
    gc.collect()


def _plant_autosave_file(tmp_path, original_file_path=None):
    autosave_path = tmp_path / "autosave.engcalc"
    data = {
        "version": "1.0",
        "metadata": {
            "title": "복구테스트",
            "created": "2026-01-01T00:00:00",
            "modified": "2026-01-01T00:05:00",
            "original_file_path": original_file_path,
        },
        "blocks": [
            {"type": "math", "id": "blk_recover", "position": [10.0, 20.0], "expression": "a = 999", "display_unit": ""},
        ],
    }
    save_document(data, str(autosave_path))
    return autosave_path


def test_accepting_recovery_restores_blocks_and_marks_modified(monkeypatch, tmp_path):
    """복구를 수락(예)하면 블록이 되살아나고, 아직 저장 전이라 "수정됨" 표시가 남아야 한다."""
    _plant_autosave_file(tmp_path, original_file_path=r"C:\docs\원본.engcalc")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes)

    win = MainWindow()
    win.show()
    for _ in range(3):
        _app.processEvents()  # _reset_modified_flag의 singleShot(0, ...)까지 처리되게 함

    restored = _math_blocks(win)
    assert len(restored) == 1
    assert restored[0].input_text() == "a = 999"
    assert win._current_file_path == r"C:\docs\원본.engcalc"
    assert win._is_modified is True  # 복구된 내용은 아직 실제 파일에 저장된 게 아님
    assert win.windowTitle().startswith("*")

    win._scene.selectionChanged.disconnect(win._on_selection_changed)
    win._scene.changed.disconnect(win._on_scene_changed)
    win._autosave_timer.stop()
    win._is_modified = False
    win.close()
    _app.processEvents()
    gc.collect()


def test_declining_recovery_deletes_autosave_and_starts_empty(monkeypatch, tmp_path):
    """복구를 거절(아니오)하면 자동 저장 파일이 지워지고 빈 문서로 시작해야 한다."""
    autosave_path = _plant_autosave_file(tmp_path)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.No)

    win = MainWindow()
    win.show()
    _app.processEvents()

    assert not autosave_path.exists()
    assert _math_blocks(win) == []
    assert win._is_modified is False

    win._scene.selectionChanged.disconnect(win._on_selection_changed)
    win._scene.changed.disconnect(win._on_scene_changed)
    win._autosave_timer.stop()
    win._is_modified = False
    win.close()
    _app.processEvents()
    gc.collect()
