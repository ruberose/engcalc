"""
도움말(사용법) 대화상자.

메뉴 > 도움말 에서 열리며, 이 프로그램의 주요 기능과 단축키를 한 화면에서
훑어볼 수 있게 보여준다. docs/사용법.txt(더 자세한 텍스트 버전)의 요약판이라고
보면 된다 — 새 기능이 추가될 때마다 이 파일과 docs/사용법.txt를 같이 갱신한다.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout

_HELP_HTML = """
<h2>EngCalc 사용법</h2>
<p>이 창은 안 닫고 켜둔 채로 작업하면서 참고할 수 있습니다.</p>

<h3>블록 만들기 / 편집</h3>
<ul>
<li><b>더블클릭</b> — 그 자리에 <b>수식 블록</b> 생성 (핵심 기능이라 기본 동작)</li>
<li><b>Ctrl + 더블클릭</b> — 그 자리에 <b>텍스트 블록</b> 생성</li>
<li>블록을 <b>더블클릭</b>하면 편집 모드로 들어감, 바깥을 클릭하면 편집 종료</li>
<li>수식 블록은 편집 중 <b>Enter</b>로도 편집을 끝낼 수 있음</li>
<li>블록 <b>드래그</b>로 이동, <b>Delete</b>/<b>Backspace</b>로 삭제</li>
<li>블록을 선택하면 우측(또는 우측 하단)에 손잡이가 나타나 폭/크기 조절 가능</li>
</ul>

<h3>수식 블록</h3>
<p>입력은 <code>a = 100</code>처럼 대입하거나, <code>a * 2 + 1</code>처럼 바로 계산합니다.
블록은 화면 위→아래, 왼→오른 순서로 계산되며, 위에서 정의한 변수를 아래 블록이 이어받습니다.</p>
<ul>
<li>연산자: <code>+ - * / ^ %</code>, 비교 <code>&lt; &gt; &lt;= &gt;= ==</code>
(곱하기는 <code>*</code>로 입력하지만 화면엔 실제 수식처럼 <code>·</code>로 표시됩니다)</li>
<li>함수: <code>sin cos tan asin acos atan sinh cosh tanh exp log ln log10 log2 sqrt cbrt root abs round ceil floor</code>
(삼각함수는 <b>도(degree)</b> 기준, 라디안 아님)</li>
<li>상수: <code>pi</code>, <code>e</code></li>
<li>변수 이름에 한글도 가능: <code>sigma_허용 = 24</code></li>
<li><b>아래첨자/위첨자</b>: <code>F_y</code>, <code>x^2</code>처럼 <code>_</code>/<code>^</code>를 쓰면 자동으로
작게 표시됩니다. 여러 글자를 묶으려면 중괄호: <code>sigma_{allow}</code>, <code>x^{10}</code></li>
<li>정의되지 않은 변수, 수식 오류는 앱이 멈추지 않고 블록 아래 빨간 글씨로 표시됩니다</li>
</ul>

<h3>단위 계산</h3>
<p>숫자 뒤에 단위를 붙이면(띄어써도, 붙여써도 인식) 단위가 있는 값으로 계산됩니다.</p>
<pre>F = 200 kN
A = 300 mm * 500 mm
sigma = F / A          -&gt; MPa로 자동 정리</pre>
<ul>
<li>길이 m·cm·mm·km·in·ft·yd, 힘 N·kN·kgf·tonf·lbf, 응력 Pa·kPa·MPa·GPa·psi·ksi,
질량 kg·g·ton·lb, 온도 degC·degF·K, 각도 deg·rad 등 지원</li>
<li><code>ton</code>은 한국 관례대로 <b>미터톤(1000kg)</b>, <code>tonf</code>(톤힘)은 9.80665 kN</li>
<li>블록을 <b>Ctrl+더블클릭</b>하면 결과의 표시 단위만 바로 바꿀 수 있음
(예: <code>5m+6m=11m</code> → <code>mm</code> 입력 → <code>5m+6m=11000mm</code>, 실제 계산값은 그대로)</li>
<li>같은 걸 속성 패널의 "표시 단위" 입력으로도 할 수 있습니다</li>
</ul>

<h3>텍스트 블록</h3>
<p>제목/설명 등 자유 서식 글을 쓸 때 씁니다. 위/아래첨자는 수식 블록과 같은 문법이지만
중괄호가 항상 필요합니다: <code>x^{2}</code>, <code>sigma_{허용}</code> (한글도 가능).</p>

<h3>이미지 블록</h3>
<p>메뉴 &gt; 파일 &gt; 이미지 삽입, 또는 탐색기에서 캔버스로 <b>드래그앤드롭</b>
(PNG/JPG/BMP/SVG 지원). 선택 후 우측 하단 손잡이로 크기 조절.</p>

<h3>실행취소 / 다시실행 / 복사 / 붙여넣기</h3>
<table cellspacing="6">
<tr><td><code>Ctrl+Z</code></td><td>실행취소</td></tr>
<tr><td><code>Ctrl+Y</code></td><td>다시실행</td></tr>
<tr><td><code>Ctrl+C</code></td><td>선택한 블록 복사</td></tr>
<tr><td><code>Ctrl+V</code></td><td>붙여넣기 (원본에서 살짝 어긋난 위치에)</td></tr>
</table>
<p>블록을 편집(타이핑) 중일 때는 이 단축키들이 편집기 자체의 텍스트 실행취소/복사/붙여넣기로 쓰입니다.</p>

<h3>파일 / PDF</h3>
<table cellspacing="6">
<tr><td><code>Ctrl+N</code></td><td>새로 만들기</td></tr>
<tr><td><code>Ctrl+O</code></td><td>열기</td></tr>
<tr><td><code>Ctrl+S</code></td><td>저장</td></tr>
<tr><td><code>Ctrl+Shift+S</code></td><td>다른 이름으로 저장</td></tr>
</table>
<p>메뉴 &gt; 파일 &gt; PDF로 내보내기 로 현재 캔버스를 A4 PDF로 저장할 수 있습니다
(내용이 길면 자동으로 여러 페이지로 나뉨).</p>

<h3>속성 패널 / 변수 목록</h3>
<p>창 오른쪽 탭에서 전환합니다. 속성 패널은 선택한 블록의 위치/크기/서식/표시 단위를
보여주고 직접 바꿀 수 있습니다. 변수 목록은 문서 전체에 정의된 변수를 한눈에 보여주며,
더블클릭하면 그 변수를 정의한 블록으로 화면이 이동합니다.</p>

<h3>화면 조작</h3>
<ul>
<li>마우스 휠 — 커서 위치 중심 확대/축소</li>
<li>Space + 드래그 — 캔버스 패닝</li>
<li>빈 캔버스 드래그 — 여러 블록 한 번에 선택(러버밴드)</li>
</ul>
"""


class HelpDialog(QDialog):
    """
    사용법을 보여주는 대화상자.

    Note:
        모달로 띄우면 이 창을 보면서 동시에 캔버스에 타이핑할 수 없어 불편하므로,
        비모달(show())로 열어서 작업 중에도 계속 참고할 수 있게 한다.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("EngCalc 사용법")
        self.resize(640, 720)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(_HELP_HTML)

        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(browser)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
