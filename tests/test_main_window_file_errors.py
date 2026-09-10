"""
app/main_window.py의 파일 열기 에러 처리 테스트.

버그체크 중 발견: 손상된 .engcalc 파일(필수 필드 누락 등)을 열면 KeyError가
그대로 위로 올라가 앱이 죽었다. "파일 I/O 에러는 사용자에게 다이얼로그로
알린다"는 코드 규칙(4.4)을 어기고 있었다.
"""

import json
import os
import tempfile

from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


def _write_json(tmp_dir: str, name: str, data) -> str:
    path = os.path.join(tmp_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def test_loading_file_with_block_missing_position_does_not_crash():
    """블록 하나에 position이 빠져 있어도 앱이 죽지 않고, 나머지 블록은 복원되어야 한다."""
    window = MainWindow()
    window.show()
    for _ in range(3):
        _app.processEvents()

    data = {
        "version": "1.0",
        "metadata": {},
        "blocks": [
            {"type": "math", "id": "blk_1", "expression": "a = 100"},  # position 없음
            {
                "type": "text",
                "id": "blk_2",
                "position": [0.0, 0.0],
                "content": "살아남아야 함",
                "style": {"font_size": 14, "bold": False},
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = _write_json(tmp_dir, "broken.engcalc", data)
        window._load_from_path(path)  # 예외를 던지면 이 테스트가 바로 실패함

    scene = window.centralWidget().scene()
    assert len(scene.items()) == 1
    assert scene.items()[0]._text == "살아남아야 함"


def test_loading_file_with_blocks_not_a_list_shows_dialog_instead_of_crashing(monkeypatch):
    """"blocks" 필드 자체가 리스트가 아닌 완전히 이상한 파일도 다이얼로그로 처리되고, 죽지 않아야 한다."""
    window = MainWindow()
    window.show()
    for _ in range(3):
        _app.processEvents()

    shown_messages = []
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args, **kwargs: shown_messages.append(args) or QMessageBox.StandardButton.Ok
    )

    data = {"version": "1.0", "metadata": {}, "blocks": "이건 리스트가 아니라 문자열임"}

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = _write_json(tmp_dir, "very_broken.engcalc", data)
        window._load_from_path(path)  # 예외를 던지면 이 테스트가 바로 실패함

    assert len(shown_messages) == 1, "에러 다이얼로그가 정확히 한 번 떠야 함"
