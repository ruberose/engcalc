# EngCalc

SMath Studio와 유사한 자유 형식(free-form) 엔지니어링 계산 문서 프로그램.
캔버스 위에 수식·텍스트·이미지 블록을 자유롭게 배치하고, 수식은 입력 즉시 실시간 계산되며 단위 변환을 자동 처리한다.

## 기술 스택
- GUI: PySide6 (Qt 6)
- 수식 계산: SymPy + Pint
- PDF 출력: ReportLab
- 파일 형식: JSON (`.engcalc`)

## 개발 상태
Phase 0 — 프로젝트 뼈대 + 빈 창 띄우기 (진행 중)

## 실행 방법
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 라이선스
MIT
