# 프로젝트: EngCalc — 엔지니어링 계산 문서 프로그램

## 1. 프로젝트 개요

SMath Studio와 유사한 **자유 형식(free-form) 엔지니어링 계산 문서 프로그램**을 Python으로 만든다.
줄(line) 기반이 아니라, 캔버스 위에 수식 블록·텍스트 블록·이미지 블록을 **자유롭게 배치**하고, 수식은 입력 즉시 실시간 계산되며, 단위 변환을 자동 처리한다.

### 핵심 목표
- SMath Studio의 **기본 사용 경험**을 재현한다 (고급 기호연산·프로그래밍 블록 등은 1차 범위 밖).
- 구조설계 엔지니어가 **개인 검산·계산 기록** 용도로 실무에 바로 쓸 수 있어야 한다.
- **PDF 출력**으로 계산서 형태의 산출물을 만들 수 있어야 한다.
- 코드를 **학습 교재처럼** 읽을 수 있게 작성한다 — 모든 모듈·클래스·함수에 한글 주석과 docstring을 충실히 단다.
- 추후 기능 확장이 쉽도록 **모듈 분리·계층 구조**를 철저히 지킨다.

### 기술 스택
| 영역 | 선택 | 이유 |
|------|------|------|
| GUI 프레임워크 | **PySide6 (Qt 6)** | 크로스플랫폼, 자유 형식 캔버스(QGraphicsScene)에 최적, LGPL이라 상업 사용 OK |
| 수식 렌더링 | **matplotlib.mathtext** 또는 **KaTeX 웹뷰 임베드** | LaTeX 문법으로 수식을 예쁘게 표시 |
| 수식 파싱/계산 | **SymPy** (기호연산) + **Pint** (단위 처리) | 둘 다 순수 Python, MIT/BSD 라이선스 |
| PDF 출력 | **ReportLab** 또는 **Qt 자체 QPrinter** | Python 네이티브 PDF 생성 |
| 파일 저장 | **JSON** (.engcalc 확장자) | 사람이 읽을 수 있고, 버전관리(git) 친화적 |

> **라이선스 참고**: 위 모든 라이브러리는 MIT/BSD/LGPL로, 개인·회사 구분 없이 자유롭게 사용·배포 가능하다. 이 프로그램 자체도 MIT로 공개할 예정이므로 라이선스 리스크는 0이다.

---

## 2. 아키텍처 — 모듈 구조

```
engcalc/
├── main.py                  # 앱 진입점 (QApplication 생성, 메인윈도우 실행)
├── app/
│   ├── __init__.py
│   ├── main_window.py       # 메인 윈도우 (메뉴바, 툴바, 상태바)
│   └── settings.py          # 사용자 설정 관리 (최근 파일, 테마 등)
│
├── canvas/
│   ├── __init__.py
│   ├── document_scene.py    # QGraphicsScene 서브클래스 — 문서 캔버스 핵심
│   ├── document_view.py     # QGraphicsView 서브클래스 — 확대/축소, 스크롤
│   └── grid.py              # 배경 격자(그리드) 그리기
│
├── blocks/                  # ★ 각 블록 타입을 독립 모듈로 분리
│   ├── __init__.py
│   ├── base_block.py        # 모든 블록의 부모 클래스 (이동, 선택, 직렬화 인터페이스)
│   ├── math_block.py        # 수식 블록 (입력 → 파싱 → 계산 → 렌더링)
│   ├── text_block.py        # 서식 있는 텍스트 블록 (제목, 설명 등)
│   ├── image_block.py       # 이미지 삽입 블록
│   ├── result_block.py      # 계산 결과 표시 전용 블록 (수식 블록에 연결)
│   └── plot_block.py        # [향후 확장] 그래프/차트 블록
│
├── engine/                  # ★ 계산 엔진 — GUI와 완전 분리
│   ├── __init__.py
│   ├── evaluator.py         # 수식 문자열 → 계산 결과 (SymPy 래퍼)
│   ├── unit_manager.py      # 단위 변환·관리 (Pint 래퍼)
│   ├── scope.py             # 변수 스코프 관리 (변수 이름 → 값 매핑)
│   ├── functions.py         # 내장 함수 레지스트리 (sin, cos, sqrt 등)
│   └── parser.py            # 입력 텍스트 → 내부 수식 표현으로 변환
│
├── io/                      # ★ 파일 입출력 — 저장/불러오기/내보내기
│   ├── __init__.py
│   ├── file_manager.py      # .engcalc 파일 저장/불러오기 (JSON 직렬화)
│   ├── pdf_exporter.py      # PDF 내보내기
│   └── template_manager.py  # [향후 확장] 계산서 템플릿 관리
│
├── ui/                      # ★ 재사용 가능한 UI 위젯
│   ├── __init__.py
│   ├── toolbar.py           # 블록 삽입 툴바
│   ├── property_panel.py    # 선택된 블록의 속성 편집 패널
│   ├── variable_inspector.py # 현재 문서의 변수 목록 표시
│   └── unit_selector.py     # 단위 선택 드롭다운/자동완성
│
├── rendering/               # ★ 수식·결과 시각 표현
│   ├── __init__.py
│   ├── math_renderer.py     # LaTeX 수식 → 이미지/SVG 변환
│   └── syntax_highlighter.py # 수식 입력 시 문법 하이라이팅
│
└── utils/
    ├── __init__.py
    ├── constants.py          # 물리 상수, 기본 설정값
    └── logger.py             # 로깅 설정
```

### 모듈 분리 원칙 (반드시 지켜야 함)

1. **engine/ 패키지는 GUI를 절대 import하지 않는다.** 계산 엔진은 터미널에서 `python -c "from engine.evaluator import ..."` 로 단독 실행·테스트할 수 있어야 한다.
2. **blocks/ 의 각 블록은 base_block.py만 상속한다.** 블록끼리 직접 참조하지 않고, 이벤트/시그널로 소통한다.
3. **io/ 패키지는 블록 객체를 직접 다루지 않는다.** 블록이 자신의 데이터를 dict로 직렬화(serialize)하면, io/는 그 dict만 읽고 쓴다.
4. **한 파일이 300줄을 넘으면 분리를 검토한다.**

---

## 3. 개발 순서 — Phase별 진행

**중요: 한 Phase가 완전히 동작하고 테스트된 후에 다음 Phase로 넘어간다. 절대 한꺼번에 전부 작성하지 않는다.**

각 Phase 완료 시:
- 해당 기능이 실제로 실행되어 눈으로 확인 가능해야 함
- 내게 "Phase N 완료" 메시지와 함께 현재 상태 스크린샷(또는 설명)을 보여줄 것
- 내가 확인 후 다음 Phase 진행을 지시함

---

### Phase 0: 프로젝트 뼈대 + 빈 창 띄우기

**목표**: 프로젝트 폴더 구조 생성, 의존성 설치, 빈 메인 윈도우가 뜨는 것 확인

만들 것:
- `engcalc/` 폴더 구조 전체 (빈 `__init__.py` 포함)
- `requirements.txt` (PySide6, sympy, pint, reportlab, matplotlib)
- `main.py` — QApplication + MainWindow (빈 창)
- `app/main_window.py` — 메뉴바(파일/편집/보기/도움말), 중앙에 빈 QGraphicsView 배치

완료 기준: `python main.py` 실행 시 격자 배경의 빈 창이 뜬다.

---

### Phase 1: 캔버스 + 텍스트 블록

**목표**: 자유 형식 캔버스 위에 텍스트 블록을 놓고 이동·편집할 수 있다.

만들 것:
- `canvas/document_scene.py` — 더블클릭 시 텍스트 블록 생성
- `canvas/document_view.py` — 마우스 휠 확대/축소, 드래그 스크롤
- `canvas/grid.py` — 배경 격자 그리기
- `blocks/base_block.py` — 공통 인터페이스: `serialize()`, `deserialize()`, 이동/선택/삭제 처리
- `blocks/text_block.py` — 더블클릭으로 편집 모드 진입, 기본 서식(볼드, 크기 변경) 지원

완료 기준: 캔버스 아무 곳이나 더블클릭 → 텍스트 블록 생성 → 드래그로 이동 → 더블클릭으로 텍스트 편집 → Delete 키로 삭제.

---

### Phase 2: 수식 블록 (핵심 기능)

**목표**: 수식 블록에 수식을 입력하면 실시간으로 계산 결과가 표시된다.

만들 것:
- `engine/parser.py` — 사용자 입력 텍스트를 SymPy 표현식으로 변환
- `engine/evaluator.py` — SymPy 표현식 계산, 에러 처리
- `engine/scope.py` — 변수 저장소 (`x = 5` 하면 이후 수식에서 x 사용 가능)
- `engine/functions.py` — 내장 함수 등록 (sin, cos, tan, sqrt, abs, log, ln, exp, pi, e 등)
- `blocks/math_block.py` — 입력 영역 + 결과 표시 영역, 입력 변경 시 자동 재계산
- `rendering/math_renderer.py` — 수식을 LaTeX로 변환하여 예쁘게 렌더링

지원할 연산:
```
기본 산술:    +, -, *, /, ^(거듭제곱), %(나머지)
비교:        >, <, >=, <=, ==
삼각함수:    sin, cos, tan, asin, acos, atan, atan2
쌍곡선:      sinh, cosh, tanh
지수/로그:   exp, log(자연), log10, log2, ln
거듭제곱:    sqrt, cbrt, n제곱근
절대값:      abs
반올림:      round, ceil, floor
상수:        pi, e
변수 대입:   x = 100,  y = x * 2
```

완료 기준: 캔버스에 수식 블록 추가 → `a = 100` 입력 → 다른 수식 블록에서 `a * sin(30)` 입력 → 결과가 자동 표시됨. 변수를 수정하면 참조하는 모든 수식이 자동 재계산됨.

---

### Phase 3: 단위 시스템

**목표**: 수식에 물리 단위를 붙여 계산하고, 단위 변환이 자동으로 처리된다.

만들 것:
- `engine/unit_manager.py` — Pint 라이브러리 래퍼
- `ui/unit_selector.py` — 단위 입력 자동완성

지원할 단위 (구조설계 중심):
```
길이:     m, cm, mm, km, in, ft, yd
면적:     m^2, cm^2, mm^2, ft^2  (자동 파생)
체적:     m^3, cm^3, L, ft^3     (자동 파생)
힘:       N, kN, MN, kgf, tonf, lbf
응력:     Pa, kPa, MPa, GPa, psi, ksi  (= N/m^2 계열)
모멘트:   N*m, kN*m, kgf*m, lbf*ft
질량:     kg, g, ton, lb
시간:     s, min, hr
온도:     degC, degF, K
각도:     deg, rad
밀도:     kg/m^3, kN/m^3
```

계산 예시 (이것들이 정상 작동해야 함):
```
F = 200 kN
b = 300 mm
h = 500 mm
A = b * h                    → 150000 mm^2
sigma = F / A                → 1.333 MPa  (단위 자동 정리)
sigma_허용 = 24 MPa
OK = sigma < sigma_허용      → True
```

완료 기준: 위 예시를 수식 블록들로 입력했을 때 단위가 자동으로 정리되고 올바른 결과가 나온다.

---

### Phase 4: 이미지 블록

**목표**: 캔버스에 이미지를 삽입·배치할 수 있다.

만들 것:
- `blocks/image_block.py` — 이미지 파일 선택, 캔버스에 표시, 크기 조절 핸들

지원 형식: PNG, JPG, BMP, SVG

완료 기준: 메뉴 또는 드래그앤드롭으로 이미지 삽입 → 캔버스에서 이동·크기 조절 가능.

---

### Phase 5: 파일 저장/불러오기

**목표**: 작업 내용을 .engcalc 파일(JSON)로 저장하고 다시 불러올 수 있다.

만들 것:
- `io/file_manager.py` — 문서 → JSON 직렬화/역직렬화
- `app/main_window.py` 수정 — 파일 메뉴(새로 만들기, 열기, 저장, 다른 이름으로 저장), 최근 파일 목록, 창 제목에 파일명 표시, 수정 감지(닫을 때 저장 여부 확인)

파일 구조 예시:
```json
{
  "version": "1.0",
  "metadata": {
    "title": "기초 전단 검토",
    "author": "주엔지니어",
    "created": "2026-09-09T14:30:00",
    "modified": "2026-09-09T15:45:00"
  },
  "blocks": [
    {
      "type": "text",
      "id": "blk_001",
      "position": [100, 50],
      "size": [400, 30],
      "content": "1. 설계조건",
      "style": {"font_size": 16, "bold": true}
    },
    {
      "type": "math",
      "id": "blk_002",
      "position": [100, 100],
      "expression": "F = 200 kN",
      "unit_display": "kN"
    },
    {
      "type": "image",
      "id": "blk_003",
      "position": [100, 300],
      "size": [300, 200],
      "image_data": "<base64 encoded>",
      "caption": "단면도"
    }
  ]
}
```

완료 기준: 수식·텍스트·이미지가 포함된 문서를 저장 → 프로그램 종료 → 다시 열기 → 모든 블록과 계산 결과가 원래대로 복원됨.

---

### Phase 6: PDF 내보내기

**목표**: 현재 문서를 PDF로 내보낸다. 구조검토서 형식처럼 깔끔하게 출력되어야 한다.

만들 것:
- `io/pdf_exporter.py` — 캔버스 내용을 PDF로 렌더링

요구사항:
- A4 용지 기준, 여백 설정 가능
- 수식은 LaTeX 렌더링된 상태 그대로 PDF에 반영
- 텍스트 서식(볼드, 크기) 유지
- 이미지 포함
- 페이지 번호 자동 삽입
- 머리글/바닥글에 문서 제목, 날짜 표시

완료 기준: 계산이 포함된 문서를 PDF로 내보내고, 그 PDF를 열었을 때 캔버스와 동일한 레이아웃이 보인다.

---

### Phase 7: 속성 패널 + 변수 목록

**목표**: 사이드 패널로 편의 기능을 제공한다.

만들 것:
- `ui/property_panel.py` — 블록 선택 시 오른쪽에 속성(위치, 크기, 서식, 단위 표시 형식 등) 편집 패널
- `ui/variable_inspector.py` — 현재 문서에 정의된 모든 변수와 값을 목록으로 표시 (변수 클릭 시 해당 블록으로 이동)

완료 기준: 블록을 클릭하면 속성 패널에서 위치·서식 수정 가능. 변수 목록에서 변수를 더블클릭하면 해당 수식 블록으로 스크롤 이동.

---

## 4. 코드 작성 규칙 (반드시 지킬 것)

### 4.1 주석과 문서화

```python
class MathBlock(BaseBlock):
    """
    수식 블록 — 사용자가 수식을 입력하면 실시간으로 계산 결과를 표시한다.

    구조:
        [입력 영역]  →  파싱  →  계산  →  [결과 표시 영역]

    사용 예:
        block = MathBlock(position=(100, 200))
        block.set_expression("F = 200 kN")
        # → 결과 영역에 "200 kN" 표시, scope에 F=200kN 등록
    """

    def evaluate(self, scope: dict) -> EvalResult:
        """
        현재 수식을 계산한다.

        Args:
            scope: 이전 블록들에서 정의된 변수 딕셔너리
                   예: {"F": 200*kN, "b": 300*mm}

        Returns:
            EvalResult: 계산 결과 (값, 단위, 에러 정보 포함)

        Note:
            이 메서드는 engine/evaluator.py의 evaluate() 함수를 내부적으로 호출한다.
            GUI 관련 코드는 여기에 넣지 않는다.
        """
```

- **모든 클래스**: docstring 필수. "이 클래스가 뭔지, 어떤 구조인지, 사용 예시" 포함.
- **모든 public 메서드**: docstring 필수. Args, Returns, Note 포함.
- **복잡한 로직**: 코드 블록 위에 `# --- 단위 변환 처리 ---` 같은 구분 주석 + 왜 이렇게 했는지 설명.
- **모든 주석과 docstring은 한글로 작성한다.**

### 4.2 네이밍 규칙

```python
# 클래스: PascalCase (영문)
class MathBlock:
class UnitManager:

# 함수/변수: snake_case (영문)
def evaluate_expression(expr_text: str) -> EvalResult:
calculated_value = ...

# 상수: UPPER_SNAKE_CASE
DEFAULT_GRID_SIZE = 20
MAX_UNDO_STEPS = 50

# 시그널: snake_case + _changed / _requested / _triggered
expression_changed = Signal(str)
recalculation_requested = Signal()
```

### 4.3 타입 힌트

모든 함수에 타입 힌트를 단다:

```python
def evaluate(self, expression: str, scope: dict[str, Any]) -> EvalResult:
    ...
```

### 4.4 에러 처리

- 수식 파싱/계산 에러는 절대 프로그램을 죽이지 않는다 → try/except로 잡아서 블록에 에러 메시지 표시.
- 파일 I/O 에러는 사용자에게 다이얼로그로 알린다.
- 모든 except는 구체적인 예외 타입을 잡는다 (bare `except:` 금지).

### 4.5 테스트

- `engine/` 패키지의 핵심 함수들은 간단한 단위 테스트를 `tests/` 폴더에 작성한다.
- 특히 단위 변환 계산은 틀리면 안 되므로, 구조설계에서 자주 쓰는 조합을 테스트 케이스로 포함한다:
  ```python
  def test_stress_calculation():
      """힘 ÷ 면적 = 응력 단위 변환 확인"""
      result = evaluate("200 kN / (300 mm * 500 mm)")
      assert abs(result.to("MPa").magnitude - 1.333) < 0.01
  ```

---

## 5. 기술적 주의사항

### 5.1 계산 순서 (Evaluation Order)

SMath Studio는 블록의 **위치(위→아래, 왼→오른)** 순서로 계산한다. 이 프로그램도 동일하게:
1. 모든 math_block을 y좌표 오름차순(같으면 x좌표 오름차순)으로 정렬
2. 순서대로 각 블록의 수식을 evaluate
3. 변수 정의(`x = ...`)가 있으면 scope에 등록
4. 이후 블록에서 해당 변수 참조 가능
5. 어떤 블록의 값이 변경되면, 그 블록 이후의 모든 블록을 재계산

### 5.2 단위 시스템 주의점

- Pint에서 온도(degC, degF)는 offset 단위라 일반 곱셈/나눗셈이 안 된다 → 온도차(delta_degC)와 절대 온도를 구분 처리해야 한다.
- `kgf`(킬로그램힘)와 `kg`(킬로그램 질량)을 혼동하지 않도록 한다. 구조설계에서 `kgf`는 매우 자주 쓰인다.
- `tonf`(톤힘 = 9.80665 kN)을 Pint 커스텀 단위로 등록해야 할 수 있다.
- 각도 함수: sin(30)에서 30을 degree로 해석할지 radian으로 해석할지 설정 가능하게 (기본값: degree — 엔지니어 관례).

### 5.3 성능

- 블록 하나 수정 시 **전체 문서를 재계산**하는 방식으로 시작한다 (단순하고 안전).
- 블록이 100개 이상일 때 성능 이슈가 생기면 그때 의존성 그래프 기반 부분 재계산으로 최적화한다.
- 1차 목표에서는 성능 최적화보다 정확성과 코드 가독성을 우선한다.

---

## 6. 향후 확장 가능성 (1차 범위 밖, 하지만 구조적으로 대비해둘 것)

아래 기능들은 지금 만들지 않지만, 나중에 추가할 수 있도록 구조를 열어둔다:

- **그래프/차트 블록** (plot_block.py) — matplotlib 임베드
- **행렬/벡터 연산** — 구조역학 강성행렬 등
- **조건문/반복문 블록** — if/for 로직
- **표(table) 블록** — 단면 제원표 등
- **템플릿 시스템** — 자주 쓰는 계산서 양식 저장
- **실행 취소/다시 실행 (Undo/Redo)** — QUndoStack 활용
- **다크 모드**
- **다국어 지원** — 현재는 한글 UI

---

## 7. 작업 방식 지시

1. **Phase 단위로 작업한다.** Phase 0부터 시작해서, 각 Phase가 완전히 동작하는 것을 확인한 후 다음으로 넘어간다.
2. **각 Phase 시작 시**, 어떤 파일을 만들/수정할 것인지 목록을 먼저 보여주고, 내 확인 후 코드를 작성한다.
3. **각 Phase 완료 시**, 실행 방법과 테스트 방법을 알려주고, 현재까지 완성된 기능을 요약해서 보여준다.
4. **코드를 작성할 때**, 위 모듈 구조와 코드 작성 규칙을 반드시 따른다.
5. **설명 없이 코드만 던지지 않는다.** "지금 뭘 만들고 있고, 왜 이렇게 만들었는지"를 항상 함께 설명한다.
6. **새로운 개념이 나오면 설명한다.** (예: QGraphicsScene이 뭔지, Signal/Slot 패턴이 뭔지 등) 이 프로젝트를 통해 내가 Python GUI 프로그래밍을 배울 수 있도록 한다.
7. **git 커밋 메시지 수준으로** 각 변경의 의도를 명확히 한다.

---

## 8. 시작하기

Phase 0부터 시작해줘. 먼저 프로젝트 폴더 구조와 requirements.txt를 만들고, 빈 메인 윈도우가 뜨는 것까지 확인하자. Phase 0에서 만들 파일 목록을 먼저 보여줘.
