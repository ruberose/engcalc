"""file_io/file_manager.py 단위 테스트."""

import json
import os
import tempfile

import pytest

from file_io.file_manager import load_document, save_document


def test_save_and_load_round_trip():
    """저장했다가 다시 읽으면 원본과 완전히 같은 dict가 나와야 한다."""
    data = {
        "version": "1.0",
        "metadata": {"title": "테스트 문서", "author": "", "created": "2026-01-01T00:00:00", "modified": "2026-01-01T00:00:00"},
        "blocks": [
            {"type": "text", "id": "blk_1", "position": [10.0, 20.0], "content": "1. 설계조건", "style": {"font_size": 14, "bold": False}},
            {"type": "math", "id": "blk_2", "position": [10.0, 60.0], "expression": "a = 100"},
        ],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "sample.engcalc")
        save_document(data, file_path)
        loaded = load_document(file_path)

    assert loaded == data


def test_save_document_writes_readable_utf8_json():
    """한글 등 유니코드 내용이 깨지지 않고 저장되어야 한다 (ensure_ascii=False)."""
    data = {"version": "1.0", "metadata": {}, "blocks": [{"type": "text", "content": "허용응력"}]}

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "korean.engcalc")
        save_document(data, file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()

    assert "허용응력" in raw  # \uXXXX 이스케이프가 아니라 실제 한글로 저장됨
    assert json.loads(raw) == data


def test_load_document_missing_file_raises():
    """존재하지 않는 파일을 읽으려 하면 예외가 그대로 올라와야 한다 (호출자가 처리)."""
    with pytest.raises(OSError):
        load_document(r"C:\없는\경로\없는파일.engcalc")


def test_load_document_invalid_json_raises():
    """JSON이 아닌 내용을 읽으면 JSONDecodeError가 올라와야 한다."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "broken.engcalc")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("이건 JSON이 아님 {{{")

        with pytest.raises(json.JSONDecodeError):
            load_document(file_path)
