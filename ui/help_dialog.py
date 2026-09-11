"""
도움말(사용법) 대화상자.

메뉴 > 도움말 에서 열리며, 두 페이지(탭)로 나뉜다:
    1. 기본 사용법 — 블록 조작, 파일/PDF, 실행취소/복사·붙여넣기 등 "이 앱을
       어떻게 조작하는지"
    2. 수식 작성법 — 연산자/함수/단위/아래첨자 등 "수식을 어떻게 쓰는지"
       (무한급수·정적분 같은 고급 계산이 어디까지 되는지, LaTeX 문법이 왜
       안 되는지도 여기 있음)

docs/사용법.txt(더 자세한 텍스트 버전)의 요약판이라고 보면 된다 — 새 기능이
추가될 때마다 이 파일과 docs/사용법.txt를 같이 갱신한다.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout

_BASIC_USAGE_HTML = """
<h2>기본 사용법</h2>
<p>이 창은 안 닫고 켜둔 채로 작업하면서 참고할 수 있습니다.
수식을 어떻게 써야 하는지는 "수식 작성법" 탭을 보세요.</p>

<h3>블록 만들기 / 편집</h3>
<ul>
<li><b>더블클릭</b> — 그 자리에 <b>수식 블록</b> 생성 (핵심 기능이라 기본 동작)</li>
<li><b>Ctrl + 더블클릭</b> — 그 자리에 <b>텍스트 블록</b> 생성</li>
<li>블록을 <b>더블클릭</b>하면 편집 모드로 들어감, 바깥을 클릭하면 편집 종료</li>
<li>수식 블록은 편집 중 <b>Enter</b>로도 편집을 끝낼 수 있음</li>
<li>블록 <b>드래그</b>로 이동, <b>Delete</b>/<b>Backspace</b>로 삭제</li>
<li>블록을 선택하면 우측(또는 우측 하단)에 손잡이가 나타나 폭/크기 조절 가능</li>
<li>수식 블록을 <b>Ctrl+더블클릭</b>하면 결과의 표시 단위만 바로 바꿀 수 있음
(예: <code>5m+6m=11m</code> → <code>mm</code> 입력 → <code>5m+6m=11000mm</code>)</li>
<li>정의되지 않은 변수, 수식 오류는 앱이 멈추지 않고 블록 아래 빨간 글씨로 표시됩니다</li>
</ul>

<h3>텍스트 블록</h3>
<p>제목/설명 등 자유 서식 글을 쓸 때 씁니다(계산 없음). 위/아래첨자 문법은
"수식 작성법" 탭을 참고하세요.</p>

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

_FORMULA_SYNTAX_HTML = """
<h2>수식 작성법</h2>
<p>수식 블록에 무엇을 어떻게 입력해야 하는지 정리했습니다. 블록 자체를
어떻게 만들고 옮기는지는 "기본 사용법" 탭을 보세요.</p>

<h3>연산자</h3>
<p><code>+ - * / ^ %</code>, 비교 <code>&lt; &gt; &lt;= &gt;= ==</code></p>
<p>곱하기는 <code>*</code>로 입력하지만 화면엔 실제 수식처럼 가운뎃점(<code>·</code>)으로
표시됩니다. 거듭제곱은 <code>^</code>(예: <code>2^10 = 1024</code>).</p>

<h3>함수 / 상수</h3>
<p><code>sin cos tan asin acos atan atan2 sinh cosh tanh exp log ln log10 log2
sqrt cbrt root abs round ceil floor</code>, 상수 <code>pi</code>, <code>e</code></p>
<p><b>삼각함수는 도(degree) 기준입니다</b> (예: <code>sin(30) = 0.5</code>, 라디안 아님).
역삼각함수의 결과도 도 단위로 나옵니다.</p>

<h3>변수 이름</h3>
<p>영문/숫자/밑줄뿐 아니라 <b>한글</b>도 쓸 수 있습니다 (예: <code>sigma_허용 = 24</code>).
블록은 화면 위→아래, 왼→오른 순서로 계산되며, 위에서 정의한 변수를 아래 블록이 이어받습니다.</p>

<h3>위첨자 / 아래첨자 ("제곱 표현법")</h3>
<p>수식 블록은 <code>_</code>(아래첨자) / <code>^</code>(위첨자) <b>바로 다음 글자 한 개만</b>
자동으로 작게 표시합니다 — mathtext(수식 렌더러)가 그렇게 동작합니다.</p>
<pre>F_y      -&gt;  F 아래에 y (아래첨자 한 글자, 정상)
x^2      -&gt;  x 위에 2  (위첨자 한 글자, 정상)
x^2y     -&gt;  x²y  ("2"만 첨자, "y"는 그 뒤에 보통 크기로 이어짐)
sigma_allow  -&gt;  sigma 아래에 "a"만 작게, "llow"는 보통 크기로 이어짐</pre>
<p><b>여러 글자를 한번에 첨자로 묶는 중괄호(<code>F_{yield}</code> 같은) 문법은
지원하지 않습니다</b> — 아래 "LaTeX 문법은 지원하지 않음" 참고. 변수 이름 자체는
<code>sigma_allow</code>처럼 얼마든지 길게 써도 계산엔 전혀 문제없고, 화면 표시만
위 규칙을 따릅니다.</p>
<p>(참고: 텍스트 블록은 반대로 <code>^{...}</code>/<code>_{...}</code> 처럼 항상 중괄호가
있어야 첨자로 인식됩니다 — 텍스트 블록은 계산이 없는 자체 표시 전용 문법이라
LaTeX 충돌 문제가 없어서 중괄호 여러 글자 묶음을 지원합니다.)</p>

<h3>LaTeX 문법은 지원하지 않음</h3>
<p><code>\\frac{a}{b}</code>, <code>\\sqrt{x}</code>, <code>\\sum</code>, <code>\\int</code> 같은
백슬래시(<code>\\</code>)나 중괄호(<code>{ }</code>) 기반 LaTeX 문법은 <b>아예 지원하지
않습니다</b> — 입력해도 예쁘게 그려지지 않고 원문 그대로 보이면서 "LaTeX 문법은
지원하지 않습니다"라는 에러가 뜹니다. (예전엔 화면엔 그럴듯하게 나오는데 계산만
안 되는 경우가 있어서 헷갈렸는데, 아예 렌더링도 같이 포기하도록 정리했습니다.)</p>
<p>대신 이 프로그램만의 함수 호출 문법을 쓰세요:</p>
<pre>\\sqrt{x}      -&gt;  sqrt(x)
\\frac{a}{b}   -&gt;  a/b
x^{10}        -&gt;  x^10   (여러 자리 숫자도 중괄호 없이)</pre>

<h3>단위 계산</h3>
<p>숫자 뒤에 단위를 붙이면(띄어써도, 붙여써도 인식) 단위가 있는 값으로 계산됩니다.</p>
<pre>F = 200 kN
A = 300 mm * 500 mm
sigma = F / A          -&gt; MPa로 자동 정리</pre>
<ul>
<li>길이 m·cm·mm·km·in·ft·yd, 힘 N·kN·kgf·tonf·lbf, 응력 Pa·kPa·MPa·GPa·psi·ksi,
질량 kg·g·ton·lb, 온도 degC·degF·K, 각도 deg·rad 등 지원</li>
<li><code>ton</code>은 한국 관례대로 <b>미터톤(1000kg)</b>, <code>tonf</code>(톤힘)은 9.80665 kN</li>
<li>같은 걸 속성 패널의 "표시 단위" 입력으로도 바꿀 수 있습니다(기본 사용법 탭 참고)</li>
</ul>

<h3>계산 가능한 수준 ("무한급수 표현법" 등 고급 계산)</h3>
<p>기본적으로는 "공학 계산서" 수준의 숫자 계산기입니다 — 위 연산자·함수·단위 계산이
공식적으로 지원·테스트된 범위입니다.</p>
<p>다만 내부적으로 SymPy(심볼릭 수학 라이브러리)를 쓰기 때문에, 공식 목록에는 없지만
실제로 동작하는 고급 계산도 있습니다:</p>
<pre>limit(1/x, x, oo)              -&gt; 0                (극한)
solve(x^2-4, x)                -&gt; [-2, 2]           (방정식 풀이)
nsolve(x^2-2, x, 1)            -&gt; 1.41421...        (수치해석)
integrate(x^2, (x, 0, 2))      -&gt; 2.66667           (구간을 지정한 정적분)
Sum(1/n^2, (n, 1, oo))         -&gt; 1.64493...        (무한급수 합)</pre>
<p>단, <code>diff(x^2, x)</code>처럼 결과에 변수가 그대로 남는 "기호식" 계산은 안 됩니다
— 이 프로그램은 결과에 변수가 남으면 무조건 "정의되지 않은 변수" 에러로 처리해서,
<b>숫자 하나로 완전히 떨어지는 결과만</b> 보여줄 수 있습니다(그래서 미분/적분도 구간·값을
지정해야 보임). 이 SymPy 직결 기능들은 공식 지원이 아니라서 단위와 섞으면 예상과 다를 수
있고, 참고용으로만 쓰는 걸 권장합니다.</p>
"""


class HelpDialog(QDialog):
    """
    사용법을 보여주는 대화상자. "기본 사용법"/"수식 작성법" 두 탭으로 나뉜다.

    Note:
        모달로 띄우면 이 창을 보면서 동시에 캔버스에 타이핑할 수 없어 불편하므로,
        비모달(show())로 열어서 작업 중에도 계속 참고할 수 있게 한다.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("EngCalc 사용법")
        self.resize(640, 720)

        tabs = QTabWidget()
        tabs.addTab(self._make_page(_BASIC_USAGE_HTML), "기본 사용법")
        tabs.addTab(self._make_page(_FORMULA_SYNTAX_HTML), "수식 작성법")

        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

    @staticmethod
    def _make_page(html: str) -> QTextBrowser:
        """탭 하나에 들어갈 QTextBrowser를 만든다."""
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(html)
        return browser
