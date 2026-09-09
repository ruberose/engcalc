"""
EngCalc 메인 윈도우 모듈.

앱의 최상위 창(QMainWindow)을 정의한다.
Phase 0에서는 메뉴바와 격자 배경의 빈 캔버스만 갖춘 뼈대 상태이며,
이후 Phase에서 canvas/, blocks/ 모듈이 실제 캔버스 동작을 채워 넣는다.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QMainWindow,
)

# --- 격자 배경 관련 상수 ---
# Phase 1의 canvas/grid.py 가 이 값을 이어받아 더 정교하게 다듬을 예정이다.
# 지금은 "빈 창에 격자 배경이 보인다"는 Phase 0 완료 기준만 만족시키면 된다.
GRID_SIZE = 20
GRID_COLOR = QColor(230, 230, 230)
BACKGROUND_COLOR = QColor(255, 255, 255)


class GridGraphicsScene(QGraphicsScene):
    """
    격자 배경을 그리는 QGraphicsScene.

    QGraphicsScene.drawBackground()를 오버라이드하여,
    보이는 영역에만 일정 간격으로 격자선을 그린다.

    사용 예:
        scene = GridGraphicsScene()
        view = QGraphicsView(scene)
    """

    def drawBackground(self, painter: QPainter, rect) -> None:
        """
        씬의 배경에 흰색 바탕과 회색 격자선을 그린다.

        Args:
            painter: Qt가 전달하는 QPainter 객체
            rect: 현재 다시 그려야 하는 영역 (QRectF)

        Note:
            성능을 위해 화면에 보이는 rect 범위 안에서만 격자선을 계산한다.
        """
        painter.fillRect(rect, QBrush(BACKGROUND_COLOR))

        pen = QPen(GRID_COLOR)
        pen.setWidth(0)
        painter.setPen(pen)

        left = int(rect.left()) - (int(rect.left()) % GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % GRID_SIZE)

        x = left
        while x < rect.right():
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += GRID_SIZE

        y = top
        while y < rect.bottom():
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += GRID_SIZE


class MainWindow(QMainWindow):
    """
    EngCalc의 메인 윈도우.

    구조:
        메뉴바 (파일/편집/보기/도움말)
        중앙: 격자 배경의 QGraphicsView (문서 캔버스)
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
        self.statusBar().showMessage("준비됨")

    def _create_menu_bar(self) -> None:
        """
        상단 메뉴바를 구성한다.

        Note:
            Phase 0에서는 메뉴 항목의 뼈대만 만든다.
            실제 동작(파일 저장, 실행 취소 등)은 해당 기능을 구현하는
            이후 Phase(파일 입출력은 Phase 5 등)에서 연결한다.
        """
        menu_bar = self.menuBar()
        menu_bar.addMenu("파일(&F)")
        menu_bar.addMenu("편집(&E)")
        menu_bar.addMenu("보기(&V)")
        menu_bar.addMenu("도움말(&H)")

    def _create_canvas(self) -> None:
        """
        중앙에 격자 배경을 가진 빈 QGraphicsView를 배치한다.

        Note:
            지금은 GridGraphicsScene을 직접 사용하지만,
            Phase 1부터는 canvas/document_scene.py의 DocumentScene이
            이 역할을 이어받는다.
        """
        scene = GridGraphicsScene(self)
        scene.setSceneRect(0, 0, 4000, 4000)

        view = QGraphicsView(scene, self)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.setCentralWidget(view)
