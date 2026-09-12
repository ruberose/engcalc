"""
rendering/symbolic_display.py 단위 테스트.

사용자 요청: "전체적으로, 계산용 문법을 쓰더라도 그 문법에 맞는 기호가
나타났으면 좋겠어" — sqrt(x) -> \\sqrt{x}, sigma -> \\sigma, a/b -> \\frac{a}{b}.

계산에 쓰이는 원문은 절대 안 바뀐다는 걸 전제로, 여기서는 표시용 변환
함수(to_symbolic_display) 자체의 문자열 결과만 검증한다. 실제 MathBlock
조립(픽스맵 생성)까지 이어지는 통합 테스트는 tests/test_math_block_display.py에
있다.
"""

from rendering.symbolic_display import to_symbolic_display

# --- 루트 계열 ---


def test_sqrt_wraps_as_radical():
    assert to_symbolic_display("sqrt(x)") == "\\sqrt{x}"


def test_sqrt_preserves_nested_expression():
    assert to_symbolic_display("sqrt(a+b)") == "\\sqrt{a+b}"


def test_cbrt_wraps_with_index_3():
    assert to_symbolic_display("cbrt(x)") == "\\sqrt[3]{x}"


def test_root_wraps_with_given_index():
    assert to_symbolic_display("root(8, 3)") == "\\sqrt[3]{8}"


def test_root_with_wrong_arg_count_is_left_unchanged():
    assert to_symbolic_display("root(8)") == "root(8)"


def test_nested_sqrt_calls_both_convert():
    assert to_symbolic_display("sqrt(sqrt(x))") == "\\sqrt{\\sqrt{x}}"


def test_sqrt_like_identifier_is_not_mistaken_for_call():
    """"myroot(x)"처럼 함수 이름의 일부로 쓰인 경우는 건드리지 않는다."""
    assert to_symbolic_display("myroot(x)") == "myroot(x)"
    assert to_symbolic_display("cbrtx(x)") == "cbrtx(x)"


def test_unbalanced_parens_after_root_function_left_unchanged():
    """괄호가 안 맞는 등 파싱이 애매하면 원문을 안전하게 그대로 둔다."""
    text = "sqrt(x"
    assert to_symbolic_display(text) == text


# --- 그리스 문자 ---


def test_greek_variable_name_becomes_symbol():
    assert to_symbolic_display("sigma") == "\\sigma"
    assert to_symbolic_display("theta") == "\\theta"
    assert to_symbolic_display("Delta") == "\\Delta"


def test_greek_name_inside_longer_identifier_is_not_mangled():
    """"pixel"의 "pi", "theta1"의 "theta" 처럼 식별자 일부로 이어지면 건드리지 않는다."""
    assert to_symbolic_display("pixel") == "pixel"
    assert to_symbolic_display("theta1") == "theta1"
    assert to_symbolic_display("etage") == "etage"


def test_greek_name_before_multichar_subscript_gets_braced():
    assert to_symbolic_display("sigma_allow") == "\\sigma_{allow}"


def test_single_char_subscript_is_left_as_is():
    """한 글자짜리 첨자는 mathtext가 이미 잘 그리므로 중괄호를 씌우지 않는다."""
    assert to_symbolic_display("F_y") == "F_y"


def test_multichar_subscript_on_non_greek_identifier_still_gets_braced():
    """그리스 문자가 아니어도, 여러 글자 첨자는 중괄호로 묶여야 한다."""
    assert to_symbolic_display("M_max") == "M_{max}"


# --- 분수 ---


def test_single_top_level_division_becomes_fraction():
    assert to_symbolic_display("a/b") == "\\frac{a}{b}"


def test_multiple_top_level_divisions_are_left_unchanged():
    """a/b/c처럼 최상위 슬래시가 2개 이상이면 묶는 방향이 모호하므로 건드리지 않는다."""
    assert to_symbolic_display("a/b/c") == "a/b/c"


def test_division_inside_parens_is_not_top_level():
    """괄호 안의 "/"는 최상위가 아니므로, 밖에 나눗셈이 없으면 분수로 안 바뀐다."""
    assert to_symbolic_display("(a/b)") == "(a/b)"


def test_fraction_sides_are_recursively_transformed():
    assert to_symbolic_display("sqrt(a)/sqrt(b)") == "\\frac{\\sqrt{a}}{\\sqrt{b}}"


def test_division_inside_sqrt_becomes_nested_fraction():
    assert to_symbolic_display("sqrt(a/b)") == "\\sqrt{\\frac{a}{b}}"


def test_malformed_fraction_like_input_left_unchanged():
    """"a/"처럼 한쪽이 비어 있으면 분수로 바꾸지 않는다."""
    assert to_symbolic_display("a/") == "a/"


# --- 안전장치: 원본에 이미 LaTeX 마크업이 있으면 손대지 않음 ---


def test_text_already_containing_backslash_is_untouched():
    text = "\\sqrt{x}"
    assert to_symbolic_display(text) == text


def test_text_already_containing_braces_is_untouched():
    text = "x^{10}"
    assert to_symbolic_display(text) == text


def test_plain_text_without_any_special_syntax_is_unchanged():
    assert to_symbolic_display("A + B") == "A + B"


def test_empty_string_is_unchanged():
    assert to_symbolic_display("") == ""


# --- 조합 ---


def test_combination_of_greek_sqrt_and_fraction():
    assert to_symbolic_display("sigma_max*sqrt(theta_min)/E") == "\\frac{\\sigma_{max}*\\sqrt{\\theta_{min}}}{E}"
