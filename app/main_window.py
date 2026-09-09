"""
EngCalc 메인 윈도우 모듈.

앱의 최상위 창(QMainWindow)을 정의한다.
실제 캔버스 동작(격자, 블록 생성/편집)은 canvas/, blocks/ 모듈이 담당하고,
이 파일은 메뉴바·상태바 등 창 자체의 뼈대만 구성한다.
"""

from PySide6.QtWidgets import QMainWindow

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
        self.statusBar().showMessage("준비됨 — 캔버스를 더블클릭해 텍스트 블록을 추가하세요")

    def _create_menu_bar(self) -> None:
        """
        상단 메뉴바를 구성한다.

        Note:
            Phase 1에서도 메뉴 항목은 아직 뼈대만 있다.
            실제 동작(파일 저장, 실행 취소 등)은 해당 기능을 구현하는
            이후 Phase(파일 입출력은 Phase 5 등)에서 연결한다.
        """
        menu_bar = self.menuBar()
        menu_bar.addMenu("파일(&F)")
        menu_bar.addMenu("편집(&E)")
        menu_bar.addMenu("보기(&V)")
        menu_bar.addMenu("도움말(&H)")

    def _create_canvas(self) -> None:
        """중앙에 문서 캔버스(DocumentScene + DocumentView)를 배치한다."""
        scene = DocumentScene()
        view = DocumentView(scene, self)
        self.setCentralWidget(view)
