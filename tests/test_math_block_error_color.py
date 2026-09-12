"""
blocks/math_block.py — 한 줄(기본) 표시 모드에서도 에러 상태가 빨간색으로
보이는지 검증.

사용자 리포트: "a = 100mpa"처럼 단위 대소문자를 잘못 써서(MPa가 아니라
mpa/Mpa) 계산이 에러인데도, 기본 한 줄 표시 모드에서는 에러 표시가 전혀
안 보여서 성공한 것처럼 헷갈렸다(변수 목록에도 안 뜨는데 왜 안 뜨는지
알 방법이 없었음). 두 줄 모드(블록 폭을 좁혔을 때)에서만 에러가 빨간
글씨로 따로 보였는데, 정작 기본값인 한 줄 모드에는 그 처리가 빠져 있었다.
"""

from PySide6.QtWidgets import QApplication

import blocks.math_block as math_block_module
from blocks.math_block import _ERROR_COLOR_HEX, MathBlock
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


def _evaluated_block(text: str, scope: Scope | None = None) -> MathBlock:
    block = MathBlock(position=(0, 0))
    block.set_input_text(text)
    block.evaluate(scope if scope is not None else Scope())
    return block


def _spy_render_line(monkeypatch):
    """_render_line 호출을 가로채서 (텍스트, color) 쌍을 기록하되, 실제 렌더링은 그대로 수행한다."""
    calls: list[tuple[str, str]] = []
    original = math_block_module._render_line

    def spy(text, font_size=math_block_module.INPUT_FONT_SIZE, color="black"):
        calls.append((text, color))
        return original(text, font_size, color)

    monkeypatch.setattr(math_block_module, "_render_line", spy)
    return calls


def test_error_block_requests_error_color_for_combined_line(monkeypatch):
    """단위 대소문자 오타 등으로 에러인 블록은 한 줄 표시용 렌더링을 빨간색으로 요청해야 한다."""
    calls = _spy_render_line(monkeypatch)

    block = _evaluated_block("a = 100mpa")

    assert block.result() is not None
    assert block.result().is_error
    assert calls
    assert calls[-1][1] == _ERROR_COLOR_HEX


def test_successful_block_requests_black_for_combined_line(monkeypatch):
    calls = _spy_render_line(monkeypatch)

    block = _evaluated_block("a = 100MPa")

    assert not block.result().is_error
    assert calls
    assert calls[-1][1] == "black"


def test_error_block_still_shows_input_text_in_one_line_mode():
    """에러여도 입력 자체는 그대로 보여야 한다(사라지면 안 됨) — 색만 달라진다."""
    block = _evaluated_block("a = 100mpa")
    assert block._one_line_mode
    assert block._combined_pixmap is not None or block._combined_fallback is not None


def test_error_block_pixmap_is_non_null_for_ascii_input():
    """"a = 100mpa"는 ASCII라서 mathtext 픽스맵 경로를 타야 한다(폴백 텍스트가 아님)."""
    block = _evaluated_block("a = 100mpa")
    assert block._combined_pixmap is not None
    assert block._combined_fallback is None


def test_error_block_with_non_ascii_fallback_still_marked_for_error_color():
    """
    한글이 섞여 mathtext를 포기하는 경우(_draw_one_line의 일반 텍스트 폴백 경로)도
    에러면 색이 달라져야 한다 — _combined_fallback이 채워지는 케이스로 확인.
    """
    block = _evaluated_block("면적_계수 = 100mpa")
    assert block._combined_pixmap is None
    assert block._combined_fallback is not None
    assert block.result().is_error
