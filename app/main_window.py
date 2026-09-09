"""
EngCalc 메인 윈도우 모듈.

앱의 최상위 창(QMainWindow)을 정의한다.
실제 캔버스 동작(격자, 블록 생성/편집)은 canvas/, blocks/ 모듈이 담당하고,
이 파일은 메뉴바·상태바 등 창 자체의 뼈대만 구성한다.
"""

from PySide6.QtWidgets import QFileDialog, QMainWindow, QMenu

from blocks.image_block import SUPPORTED_EXTENSIONS
from canvas.document_scene import DocumentScene
from canvas.document_view import DocumentView

#: QFileDialog에 보여줄 확장자 필터 문자열 (예: "*.png *.jpg *.jpeg *.bmp *.svg").
_IMAGE_FILE_FILTER = "이미지 파일 (" + " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS) + ")"


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
        """메인 윈도우를 초기화하고 캔버스·메뉴바·상태바를 배치한다."""
        super().__init__()

        self.setWindowTitle("EngCalc")
        self.resize(1200, 800)

        # 메뉴의 "이미지 삽입" 액션이 self._scene/self._view를 참조하므로
        # 캔버스를 먼저 만들어야 한다.
        self._create_canvas()
        self._create_menu_bar()
        self.statusBar().showMessage(
            "준비됨 — 더블클릭: 수식 블록 추가 / Ctrl+더블클릭: 텍스트 블록 추가"
        )

    def _create_canvas(self) -> None:
        """
        중앙에 문서 캔버스(DocumentScene + DocumentView)를 배치한다.

        Note:
            QGraphicsView는 씬을 "소유"하지 않고 연결만 한다 — 그래서 scene을
            지역 변수로만 두면, 이 메서드가 끝나는 순간 파이썬 참조가 사라져
            가비지 컬렉터가 씬을 지워버린다(창은 뜨지만 캔버스가 먹통이 됨).
            self._scene / self._view에 저장해서 창이 살아있는 동안 계속 살아있게 한다.
        """
        self._scene = DocumentScene()
        self._view = DocumentView(self._scene, self)
        self.setCentralWidget(self._view)

    def _create_menu_bar(self) -> None:
        """
        상단 메뉴바를 구성한다.

        Note:
            대부분의 메뉴 항목은 아직 구현 전이다(파일 저장 등은 Phase 5).
            빈 채로 두면 "고장난 것"처럼 보이므로 비활성화된 안내 항목을 넣어둔다.
            "파일 > 이미지 삽입"만 Phase 4에서 실제로 동작한다.
        """
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("파일(&F)")
        insert_image_action = file_menu.addAction("이미지 삽입(&I)...")
        insert_image_action.triggered.connect(self._on_insert_image)
        file_menu.addSeparator()
        self._add_placeholder(file_menu)

        for title in ("편집(&E)", "보기(&V)", "도움말(&H)"):
            menu = menu_bar.addMenu(title)
            self._add_placeholder(menu)

    def _add_placeholder(self, menu: QMenu) -> None:
        """메뉴에 "(구현 예정)" 비활성 항목을 하나 추가한다."""
        placeholder = menu.addAction("(구현 예정)")
        placeholder.setEnabled(False)

    def _on_insert_image(self) -> None:
        """
        파일 선택 대화상자를 띄워 이미지를 고르게 하고, 캔버스 중앙에 삽입한다.

        Note:
            드래그앤드롭(canvas/document_view.py)과 달리 "놓은 위치"가 없으므로,
            현재 화면에 보이는 캔버스 영역의 중앙에 넣는다.
        """
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self, "이미지 삽입", "", _IMAGE_FILE_FILTER
        )
        if not file_path:
            return  # 사용자가 취소함

        visible_center = self._view.mapToScene(self._view.viewport().rect().center())
        block = self._scene.create_image_block_from_file(visible_center, file_path)
        if block is None:
            self.statusBar().showMessage(f"이미지를 불러올 수 없습니다: {file_path}", 5000)
