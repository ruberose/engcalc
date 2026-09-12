"""
pytest 공통 설정.

MainWindow가 뜰 때마다 자동 저장 파일이 남아있는지 확인해서, 있으면 복구할지
묻는 QMessageBox를 띄운다(app/main_window.py의 _check_autosave_recovery).
이게 사용자의 실제 홈 디렉터리(~/.engcalc/autosave.engcalc)를 그대로 보게
두면 — 실사용 중 앱이 한 번이라도 비정상 종료돼서 그 파일이 남아있으면 —
그 이후로 MainWindow()를 만드는 모든 테스트가 (아무도 응답하지 않는) 확인
팝업에서 멈춰버릴 수 있다. 그래서 모든 테스트가 자동으로 격리된 임시 경로를
쓰게 만들어 실제 사용자 파일을 절대 건드리지 않게 한다.

마찬가지로 app/settings.py는 최근 파일 목록을 QSettings(=Windows 레지스트리/
macOS·Linux 설정 파일)에 저장한다 — 격리해두지 않으면 파일을 저장/여는
테스트마다(_save_to_path()/_load_from_path()가 add_recent_file()을 부름)
실제 사용자의 최근 파일 목록이 테스트 데이터로 덮어써진다. INI 파일 기반의
임시 QSettings로 돌려서 실제 설정을 절대 건드리지 않게 한다.

app/main_window.py는 클립보드 이미지 붙여넣기(Ctrl+V) 기능 때문에
QApplication.clipboard()도 읽는다 — 실제 OS 클립보드를 그대로 두면,
테스트 실행 컴퓨터에 우연히 이미지가 복사돼 있을 때(스크린샷 도구 등)
"내부 블록 복사 -> 붙여넣기" 테스트가 실제로는 이미지 붙여넣기 경로를
타서 실패한다(직접 겪은 문제). 그래서 가짜 클립보드로 바꿔 격리한다.
"""

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def isolated_autosave_path(tmp_path, monkeypatch):
    """모든 테스트에서 자동 저장 파일 경로를 이 테스트 전용 임시 폴더로 돌린다."""
    fake_path = str(tmp_path / "autosave.engcalc")
    monkeypatch.setattr("app.main_window.autosave_file_path", lambda: fake_path)


@pytest.fixture(autouse=True)
def isolated_qsettings(tmp_path, monkeypatch):
    """모든 테스트에서 QSettings(최근 파일 등)를 이 테스트 전용 임시 INI 파일로 돌린다."""
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr("app.settings._settings", lambda: QSettings(ini_path, QSettings.Format.IniFormat))


class _FakeClipboard:
    """실제 OS 클립보드 대신 쓰는 가짜 — image()/setText()/text()만 흉내 낸다(지금 코드가 그것만 씀)."""

    def __init__(self) -> None:
        self._image = QImage()
        self._text = ""

    def image(self) -> QImage:
        return self._image

    def set_image(self, image: QImage) -> None:
        self._image = image

    def setText(self, text: str) -> None:  # noqa: N802 (QClipboard의 실제 메서드 이름과 맞춤)
        self._text = text

    def text(self) -> str:
        return self._text


@pytest.fixture(autouse=True)
def isolated_clipboard(monkeypatch):
    """
    모든 테스트에서 QApplication.clipboard()를 가짜로 돌려서 실제 OS 클립보드를
    절대 건드리지 않는다. 클립보드 이미지 붙여넣기를 직접 검증하고 싶은
    테스트는 이 fixture가 돌려주는 객체의 set_image()로 이미지를 채우면 된다.
    """
    fake = _FakeClipboard()
    monkeypatch.setattr(QApplication, "clipboard", staticmethod(lambda: fake))
    return fake
