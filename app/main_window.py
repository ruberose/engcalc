"""
EngCalc 메인 윈도우 모듈.

앱의 최상위 창(QMainWindow)을 정의한다.
실제 캔버스 동작(격자, 블록 생성/편집)은 canvas/, blocks/ 모듈이 담당하고,
이 파일은 메뉴바·상태바 등 창 자체의 뼈대만 구성한다.
"""

from PySide6.QtWidgets import QMainWindow, QMenu

from canvas.document_scene import DocumentScene
from canvas.document_view import DocumentView


class MainWindow(QMainWindow):
    """
    EngCalc의 메인 윈도우.

    구조:
        메뉴바 (파일/편집/보기/도움말)
        중앙: DocumentView + DocumentScene (문서 캔버스)
        상태바

    사용 예:
        window = MainWindow()
        window.show()
    """

    def __init__(self) -> None:
        """메인 윈도우를 초기화하고 메뉴바·캔버스·상태바를 배치한다."""
        super().__init__()

        self.setWindowTitle("EngCalc")
        self.resize(1200, 800)

        self._create_menu_bar()
        self._create_canvas()
        self.statusBar().showMessage(
            "준비됨 — 더블클릭: 수식 블록 추가 / Ctrl+더블클릭: 텍스트 블록 추가"
        )

    def _create_menu_bar(self) -> None:
        """
        상단 메뉴바를 구성한다.

        Note:
            실제 동작(파일 저장, 실행 취소 등)은 해당 기능을 구현하는
            이후 Phase(파일 입출력은 Phase 5 등)에서 연결한다. 그 전까지는
            메뉴를 열었을 때 완전히 빈 채로 보이면 "고장난 것" 처럼 보이므로,
            비활성화된 안내용 항목을 하나씩 넣어 "아직 준비 중"임을 알려준다.
        """
        menu_bar = self.menuBar()
        for title in ("파일(&F)", "편집(&E)", "보기(&V)", "도움말(&H)"):
            menu = menu_bar.addMenu(title)
            self._add_placeholder(menu)

    def _add_placeholder(self, menu: QMenu) -> None:
        """메뉴에 "(구현 예정)" 비활성 항목을 하나 추가한다."""
        placeholder = menu.addAction("(구현 예정)")
        placeholder.setEnabled(False)

    def _create_canvas(self) -> None:
        """
        중앙에 문서 캔버스(DocumentScene + DocumentView)를 배치한다.

        Note:
            QGraphicsView는 씬을 "소유"하지 않고 연결만 한다 — 그래서 scene을
            지역 변수로만 두면, 이 메서드가 끝나는 순간 파이썬 참조가 사라져
            가비지 컬렉터가 씬을 지워버린다(창은 뜨지만 캔버스가 먹통이 됨).
            self._scene에 저장해서 창이 살아있는 동안 씬도 계속 살아있게 한다.
        """
        self._scene = DocumentScene()
        view = DocumentView(self._scene, self)
        self.setCentralWidget(view)
