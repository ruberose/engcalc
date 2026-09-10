"""
사용자 설정 관리 — 최근 파일 목록 등을 앱을 껐다 켜도 유지되게 저장한다.

Qt의 QSettings를 그대로 활용한다. Windows에서는 레지스트리에,
macOS/Linux에서는 설정 파일에 저장되어 플랫폼별 코드를 따로 쓸 필요가 없다.
"""

from PySide6.QtCore import QSettings

#: 최근 파일 목록에 남겨둘 최대 개수.
MAX_RECENT_FILES = 10

_ORGANIZATION = "EngCalc"
_APPLICATION = "EngCalc"
_RECENT_FILES_KEY = "recent_files"


def _settings() -> QSettings:
    return QSettings(_ORGANIZATION, _APPLICATION)


def get_recent_files() -> list[str]:
    """최근에 연/저장한 파일 경로 목록을 최신순으로 반환한다."""
    files = _settings().value(_RECENT_FILES_KEY, [])
    if not files:
        return []
    # QSettings는 항목이 하나뿐이면 리스트가 아니라 문자열로 돌려주기도 한다.
    if isinstance(files, str):
        return [files]
    return list(files)


def add_recent_file(file_path: str) -> None:
    """파일 경로를 최근 목록 맨 앞에 추가한다 (기존에 있었으면 앞으로 옮기고, 최대 개수를 유지)."""
    files = [f for f in get_recent_files() if f != file_path]
    files.insert(0, file_path)
    _settings().setValue(_RECENT_FILES_KEY, files[:MAX_RECENT_FILES])


def clear_recent_files() -> None:
    """최근 파일 목록을 비운다."""
    _settings().setValue(_RECENT_FILES_KEY, [])
