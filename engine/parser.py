"""
사용자 입력 텍스트를 (변수명, 수식 문자열)로 분리한다.

"a = 100" 같은 대입문에서 '=' 하나(==, >=, <= 는 제외)를 찾아
왼쪽을 변수명으로, 오른쪽을 실제 계산할 수식으로 나눈다.
변수명에는 한글도 쓸 수 있다 (예: sigma_허용) — 구조설계 계산서에서
"허용응력", "소요철근량" 처럼 한글 첨자를 쓰는 관례를 지원하기 위함.
"""

import re
from dataclasses import dataclass

# 첫 글자: 숫자가 아닌 "단어" 문자(유니코드 한글 포함), 이후: 단어 문자(숫자 포함) 또는 밑줄.
# '='는 있지만 바로 뒤에 또 '='가 오지 않는 경우만 대입으로 본다 (==, >=, <= 와 구분하기 위함).
_ASSIGNMENT_PATTERN = re.compile(r"^\s*([^\W\d]\w*)\s*=(?!=)\s*(.*)$", re.UNICODE)

# 계산기 습관대로 맨 끝에 "="만 붙이는 경우(예: "32mm + 42mm =")를 위한 패턴.
# ==, <=, >=, != 의 일부인 '='는 건드리면 안 되므로, 바로 앞이 =/</>/! 가 아닐 때만 지운다.
_TRAILING_EQUALS_PATTERN = re.compile(r"(?<![=<>!])=\s*$")


@dataclass
class ParsedInput:
    """입력 한 줄을 (변수명, 수식)으로 분리한 결과."""

    variable_name: str | None
    expression_text: str


def strip_trailing_calculator_equals(text: str) -> str:
    """
    계산기 습관대로 맨 끝에 "="만 붙이는 경우(예: "32mm + 42mm =")의 그 trailing
    "="를 지운다. 이 프로그램은 "="를 안 눌러도 자동으로 계산되므로 필요 없다.

    ==, <=, >=, != 의 일부인 '='는 건드리지 않는다.

    Note:
        blocks/math_block.py도 이 함수를 그대로 써서, 계산에 넘기는 수식뿐 아니라
        화면에 표시하는 입력 원문 자체에서도 이 trailing "="를 지운다 — 안 그러면
        입력 줄 끝의 "="와 그 아래 결과 줄의 "="가 겹쳐 보여서 등호가 두 번
        있는 것처럼 보이는 문제가 있었다(버그체크 중 발견).
    """
    return _TRAILING_EQUALS_PATTERN.sub("", text).rstrip()


def parse_input(text: str) -> ParsedInput:
    """
    입력 문자열이 "이름 = 수식" 형태면 (이름, 수식)으로, 아니면 (None, 전체)로 나눈다.

    Args:
        text: 사용자가 입력한 원본 문자열

    Returns:
        ParsedInput(variable_name, expression_text)

    사용 예:
        parse_input("a = 100")             -> ParsedInput("a", "100")
        parse_input("a * sin(30)")         -> ParsedInput(None, "a * sin(30)")
        parse_input("sigma == sigma_허용")  -> ParsedInput(None, "sigma == sigma_허용")
        parse_input("32mm + 42mm =")       -> ParsedInput(None, "32mm + 42mm")
    """
    text = strip_trailing_calculator_equals(text)

    match = _ASSIGNMENT_PATTERN.match(text)
    if match:
        variable_name, expression_text = match.groups()
    else:
        variable_name, expression_text = None, text

    return ParsedInput(variable_name=variable_name, expression_text=expression_text)
