"""
수식 블록의 곱하기(*) 표시를 실제 수식처럼 가운뎃점(·)으로 바꾸는 기능 검증.

사용자 요청: "*로 곱하기 표시를 하잖아? 근데 실제 수식에서는 곱은 점이잖아?
이부분을 반영해줘"

화면에 보여줄 때만 "*" -> "·"로 바꾸고, 계산에 쓰이는 원문(input_text)이나
직렬화되는 값은 그대로 "*"를 유지해야 한다(안 그러면 다시 열었을 때 SymPy가
"·"를 곱셈으로 못 알아듣고 파싱에 실패한다).
"""

from PySide6.QtWidgets import QApplication

from blocks.math_block import MathBlock, _display_text
from engine.scope import Scope

_app = QApplication.instance() or QApplication([])


def test_display_text_replaces_asterisk_with_middle_dot():
    """_display_text()는 "*"를 가운뎃점으로 바꾸고, 그 외 문자는 손대지 않는다."""
    assert _display_text("A*B") == "A·B"
    assert _display_text("2m*3*4kN") == "2m·3·4kN"
    assert _display_text("A + B") == "A + B"  # "*" 없으면 그대로


def test_stored_input_text_keeps_literal_asterisk():
    """블록에 저장되는 원문(계산에 쓰임)은 "*" 그대로 유지되어야 한다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("A*B")
    assert block.input_text() == "A*B"


def test_evaluation_still_works_after_display_substitution():
    """화면 표시가 바뀌어도 실제 곱셈 계산 결과는 그대로여야 한다."""
    scope = Scope()
    a = MathBlock(position=(0, 0))
    a.set_input_text("A = 5")
    a.evaluate(scope)
    b = MathBlock(position=(0, 60))
    b.set_input_text("B = 6")
    b.evaluate(scope)
    q = MathBlock(position=(0, 120))
    q.set_input_text("A*B")
    q.evaluate(scope)

    assert q.result() is not None
    assert not q.result().is_error
    assert float(q.result().value) == 30.0


def test_fallback_text_shows_middle_dot_for_non_ascii_expression():
    """
    mathtext가 포기하는 한글 섞인 수식(일반 텍스트 폴백)도 "·"로 보여야 한다.

    "면적_계수"처럼 한글이 섞이면 mathtext 렌더링을 포기하고 일반 텍스트로
    대체하는데(rendering/math_renderer.py), 그 대체 텍스트에도 가운뎃점이
    적용되어야 한다.
    """
    block = MathBlock(position=(0, 0))
    block.set_input_text("면적_계수*2")
    assert block._input_pixmap is None
    assert block._input_fallback is not None
    assert "·" in block._input_fallback
    assert "*" not in block._input_fallback


def test_combined_line_display_uses_middle_dot():
    """"입력 = 결과" 합친 줄에서도 입력 쪽 "*"가 가운뎃점으로 보여야 한다."""
    scope = Scope()
    a = MathBlock(position=(0, 0))
    a.set_input_text("A = 5")
    a.evaluate(scope)
    b = MathBlock(position=(0, 60))
    b.set_input_text("B = 6")
    b.evaluate(scope)
    q = MathBlock(position=(0, 120))
    q.set_input_text("A*B")
    q.evaluate(scope)

    # ASCII 수식이라 mathtext가 성공해서 pixmap으로 렌더링됨 (fallback이 아님)
    assert q._combined_pixmap is not None or q._combined_fallback is not None
    if q._combined_fallback is not None:
        assert "·" in q._combined_fallback
        assert "*" not in q._combined_fallback


def test_serialize_preserves_literal_asterisk():
    """직렬화(저장)되는 값도 "*" 그대로여야 다시 열었을 때 계산이 된다."""
    block = MathBlock(position=(0, 0))
    block.set_input_text("A*B")
    data = block.serialize()
    assert data["expression"] == "A*B"
