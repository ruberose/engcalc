"""
캔버스 배경 격자(그리드) 그리기.

QGraphicsScene.drawBackground()에서 호출되는 순수 함수 형태로 만들어서,
격자 관련 로직을 캔버스 코드와 분리해 재사용·테스트하기 쉽게 한다.
"""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

# 격자 간격(px)과 색상. 추후 app/settings.py에서 사용자가 바꿀 수 있게 뺄 수 있다.
GRID_SIZE = 20
GRID_COLOR = QColor(230, 230, 230)
BACKGROUND_COLOR = QColor(255, 255, 255)


def draw_grid(painter: QPainter, rect: QRectF) -> None:
    """
    주어진 영역(rect)에 흰 배경과 회색 격자선을 그린다.

    Args:
        painter: 그리기에 사용할 QPainter (씬이 이미 좌표계를 설정해서 넘겨준다)
        rect: 다시 그려야 하는 영역. 이 영역 밖은 계산하지 않아 성능을 아낀다.

    Note:
        격자선은 항상 GRID_SIZE의 배수 위치에서 시작하도록,
        rect의 좌상단 좌표를 GRID_SIZE로 나눈 나머지만큼 앞으로 당겨서 그린다.
        그렇지 않으면 스크롤할 때마다 격자 위치가 화면 기준으로 흔들려 보인다.
    """
    painter.fillRect(rect, QBrush(BACKGROUND_COLOR))

    pen = QPen(GRID_COLOR)
    pen.setWidth(0)  # 0 = 확대/축소와 무관하게 항상 1px로 그려지는 코스메틱 펜
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
