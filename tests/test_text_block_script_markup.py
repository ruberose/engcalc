"""
TextBlock의 위첨자/아래첨자("^{...}", "_{...}") 마크업 기능 검증.

사용자 요청: "텍스트 쓸 떄 위첨자, 아래첨자 할 수 있나?"
MathBlock의 수식 표기(^, _)와 같은 관례를 따르되, 중괄호로 범위를 명시한다.
"""

from PySide6.QtWidgets import QApplication

from blocks.text_block import DEFAULT_TEXT, TextBlock, _tokenize_script_markup

_app = QApplication.instance() or QApplication([])


def test_tokenize_plain_text_has_single_normal_token():
    """마크업이 없으면 토큰 하나("normal")로만 이루어진다."""
    assert _tokenize_script_markup("일반 텍스트") == [("normal", "일반 텍스트")]


def test_tokenize_empty_text_returns_single_normal_token():
    """빈 문자열도 자리를 차지해야 하므로 빈 "normal" 토큰 하나를 돌려준다."""
    assert _tokenize_script_markup("") == [("normal", "")]


def test_tokenize_superscript_markup():
    """"x^{2}"는 (normal, "x") + (super, "2")로 쪼개진다."""
    assert _tokenize_script_markup("x^{2}") == [("normal", "x"), ("super", "2")]


def test_tokenize_subscript_markup():
    """"sigma_{허용}"은 (normal, "sigma") + (sub, "허용")으로 쪼개진다."""
    assert _tokenize_script_markup("sigma_{허용}") == [("normal", "sigma"), ("sub", "허용")]


def test_tokenize_mixed_markup_with_trailing_text():
    """위첨자/아래첨자 뒤에 일반 텍스트가 더 있어도 정확히 이어붙는다."""
    tokens = _tokenize_script_markup("x^{2} + y_{1} = 10")
    assert tokens == [
        ("normal", "x"),
        ("super", "2"),
        ("normal", " + y"),
        ("sub", "1"),
        ("normal", " = 10"),
    ]


def test_tokenize_unclosed_markup_is_left_as_normal_text():
    """중괄호가 안 닫히면 마크업으로 인식하지 않고 그대로 일반 텍스트로 남는다."""
    assert _tokenize_script_markup("x^{2") == [("normal", "x^{2")]


def test_layout_plain_text_matches_font_metrics_height():
    """마크업이 없는 텍스트는 위/아래로 삐져나오지 않아 본문 폰트 높이 그대로다."""
    block = TextBlock()
    block.set_text("일반 텍스트")
    width, height, segments = block._layout()
    assert len(segments) == 1
    assert segments[0][3] == "일반 텍스트"
    assert width > 0
    assert height > 0


def test_layout_with_superscript_produces_multiple_segments():
    """위첨자가 있으면 segment가 여러 개로 나뉘고, 위첨자용 폰트는 본문보다 작다."""
    block = TextBlock()
    block.set_text("x^{2}")
    _width, _height, segments = block._layout()
    assert len(segments) == 2
    (_x0, _y0, font_normal, text0), (_x1, y1, font_super, text1) = segments
    assert text0 == "x"
    assert text1 == "2"
    assert font_super.pointSize() < font_normal.pointSize()
    # 위첨자는 본문 baseline보다 위(작은 y)에 그려져야 한다
    assert y1 < _y0


def test_layout_with_subscript_lowers_baseline():
    """아래첨자는 본문 baseline보다 아래(큰 y)에 그려져야 한다."""
    block = TextBlock()
    block.set_text("sigma_{허용}")
    _width, _height, segments = block._layout()
    (_x0, y0, _f0, _t0), (_x1, y1, _f1, _t1) = segments
    assert y1 > y0


def test_layout_never_produces_negative_y_after_shift():
    """위첨자가 본문 위로 삐져나와도 boundingRect 안에 들어오도록 y가 모두 0 이상이어야 한다."""
    block = TextBlock()
    block.set_text("x^{2}")
    _width, _height, segments = block._layout()
    assert all(y >= 0 for _x, y, _f, _t in segments)


def test_bounding_rect_accounts_for_script_markup():
    """위/아래첨자가 있는 텍스트도 boundingRect가 실제 그려지는 영역을 전부 포함해야 한다."""
    block = TextBlock()
    block.set_text("x^{2}")
    rect = block.boundingRect()
    assert rect.width() > 0
    assert rect.height() > 0


def test_serialize_deserialize_preserves_markup_as_plain_string():
    """직렬화 형식은 여전히 평문 문자열이라, 기존 저장 파일과 완전히 호환된다."""
    block = TextBlock()
    block.set_text("x^{2} + y_{1}")
    data = block.serialize()
    assert data["content"] == "x^{2} + y_{1}"

    restored = TextBlock()
    restored.deserialize(data)
    assert restored.text() == "x^{2} + y_{1}"


def test_default_text_has_no_markup_and_renders_as_single_segment():
    """기본 텍스트("텍스트를 입력하세요")는 마크업이 없어 segment 하나로 그려진다."""
    block = TextBlock()
    assert block.text() == DEFAULT_TEXT
    _width, _height, segments = block._layout()
    assert len(segments) == 1
