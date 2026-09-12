"""
최근 파일(메뉴 > 파일 > 최근 파일) 기능 검증.

사용자 리포트: "최근파일 기능이 구현예정으로 되어있더라고" — 실제로는
app/settings.py(get_recent_files/add_recent_file)와 저장/열기 흐름
(app/main_window.py의 add_recent_file() 호출)은 이미 다 구현돼 있었지만,
목록이 비어 있을 때 메뉴에 (다른 미구현 기능을 위해 만들어둔) 범용
"(구현 예정)" 자리표시자를 그대로 재사용하고 있어서 "안 만들어진 기능"처럼
보였다 — 여기서는 그 표시를 "(최근 파일 없음)"으로 정확히 바꾸고, 그동안
없었던 "최근 파일 지우기"도 같이 추가했다.

tests/conftest.py의 autouse fixture가 QSettings를 이 테스트 전용 임시
INI 파일로 돌려두므로, 실제 사용자의 최근 파일 목록(레지스트리)은 전혀
건드리지 않는다.
"""

import gc

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow
from app.settings import MAX_RECENT_FILES, add_recent_file, clear_recent_files, get_recent_files

_app = QApplication.instance() or QApplication([])


# --- app/settings.py ---


def test_get_recent_files_starts_empty():
    assert get_recent_files() == []


def test_add_recent_file_puts_newest_first():
    add_recent_file("a.engcalc")
    add_recent_file("b.engcalc")
    assert get_recent_files() == ["b.engcalc", "a.engcalc"]


def test_add_recent_file_moves_existing_entry_to_front_without_duplicating():
    add_recent_file("a.engcalc")
    add_recent_file("b.engcalc")
    add_recent_file("a.engcalc")  # 다시 연/저장함
    assert get_recent_files() == ["a.engcalc", "b.engcalc"]


def test_add_recent_file_caps_at_max_count():
    for i in range(MAX_RECENT_FILES + 5):
        add_recent_file(f"file{i}.engcalc")
    recent = get_recent_files()
    assert len(recent) == MAX_RECENT_FILES
    assert recent[0] == f"file{MAX_RECENT_FILES + 4}.engcalc"  # 가장 최근 것이 맨 앞


def test_clear_recent_files_empties_list():
    add_recent_file("a.engcalc")
    assert get_recent_files() != []

    clear_recent_files()
    assert get_recent_files() == []


# --- MainWindow 메뉴 연동 ---


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


def test_empty_recent_files_shows_accurate_placeholder_not_todo(window):
    """빈 목록일 때 "(구현 예정)"이 아니라 "(최근 파일 없음)"이 떠야 한다(사용자가 헷갈린 지점)."""
    actions = window._recent_files_menu.actions()
    assert len(actions) == 1
    assert actions[0].text() == "(최근 파일 없음)"
    assert not actions[0].isEnabled()
    assert "구현 예정" not in actions[0].text()


def test_saving_a_file_adds_it_to_recent_files_menu(window, tmp_path):
    file_path = str(tmp_path / "doc.engcalc")
    assert window._save_to_path(file_path)

    actions = window._recent_files_menu.actions()
    labels = [a.text() for a in actions]
    assert file_path in labels


def test_clicking_recent_file_action_reopens_it(window, tmp_path, monkeypatch):
    file_path = str(tmp_path / "doc.engcalc")
    window._save_to_path(file_path)
    window._current_file_path = None  # "다른 문서"를 보고 있는 척

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)

    recent_action = next(a for a in window._recent_files_menu.actions() if a.text() == file_path)
    recent_action.trigger()
    _app.processEvents()

    assert window._current_file_path == file_path


def test_opening_missing_recent_file_shows_warning_without_crashing(window, tmp_path, monkeypatch):
    missing_path = str(tmp_path / "does_not_exist.engcalc")
    add_recent_file(missing_path)
    window._rebuild_recent_files_menu()

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: warned.append(1))

    window._open_recent_file(missing_path)

    assert warned == [1]


def test_clear_recent_files_menu_action_empties_list_and_resets_menu(window, tmp_path):
    file_path = str(tmp_path / "doc.engcalc")
    window._save_to_path(file_path)
    assert get_recent_files() != []

    clear_action = next(a for a in window._recent_files_menu.actions() if a.text() == "최근 파일 지우기")
    clear_action.trigger()

    assert get_recent_files() == []
    actions = window._recent_files_menu.actions()
    assert len(actions) == 1
    assert actions[0].text() == "(최근 파일 없음)"


def test_clear_recent_files_action_only_shown_when_list_has_entries(window):
    labels = [a.text() for a in window._recent_files_menu.actions()]
    assert "최근 파일 지우기" not in labels
