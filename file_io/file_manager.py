"""
.engcalc 파일(JSON) 저장/불러오기.

블록 객체(TextBlock, MathBlock, ...)는 전혀 알지 못한다 (모듈 분리 원칙 3번).
canvas/document_scene.py가 블록들을 이미 dict로 직렬화해서 넘겨주면,
이 모듈은 그 dict를 JSON 파일로 쓰고 읽는 일만 한다.

파일 I/O 에러(권한 없음, 디스크 없음 등)는 여기서 잡지 않고 그대로 위로
던진다 — "파일 I/O 에러는 사용자에게 다이얼로그로 알린다"(코드 규칙 4.4)는
호출하는 쪽인 app/main_window.py의 책임이기 때문이다.
"""

import json
from typing import Any


def save_document(data: dict[str, Any], file_path: str) -> None:
    """
    문서 dict를 .engcalc(JSON) 파일로 저장한다.

    Args:
        data: {"version", "metadata", "blocks"}를 담은 dict
        file_path: 저장할 파일 경로
    """
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_document(file_path: str) -> dict[str, Any]:
    """
    .engcalc(JSON) 파일을 읽어 dict로 반환한다.

    Args:
        file_path: 불러올 파일 경로

    Returns:
        저장할 때와 같은 구조의 dict
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
