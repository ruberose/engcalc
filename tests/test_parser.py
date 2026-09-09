"""engine/parser.py 단위 테스트."""

from engine.parser import parse_input


def test_simple_assignment():
    """'이름 = 값' 형태를 변수명과 수식으로 정확히 나누는지 확인한다."""
    result = parse_input("a = 100")
    assert result.variable_name == "a"
    assert result.expression_text == "100"


def test_expression_without_assignment():
    """대입이 아닌 순수 수식은 변수명 없이 통째로 넘어와야 한다."""
    result = parse_input("a * sin(30)")
    assert result.variable_name is None
    assert result.expression_text == "a * sin(30)"


def test_equality_is_not_treated_as_assignment():
    """'=='는 대입이 아니라 비교 연산이므로 변수명/수식으로 쪼개면 안 된다."""
    result = parse_input("sigma == sigma_허용")
    assert result.variable_name is None
    assert result.expression_text == "sigma == sigma_허용"


def test_korean_variable_name():
    """한글이 섞인 변수명(sigma_허용 등)도 대입 왼쪽으로 인식해야 한다."""
    result = parse_input("sigma_허용 = 24")
    assert result.variable_name == "sigma_허용"
    assert result.expression_text == "24"
