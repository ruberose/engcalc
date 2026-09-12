"""
캔버스 내용을 PNG 이미지로 내보낸다.

file_io/pdf_exporter.py와 같은 원리(QGraphicsScene을 그대로 렌더링)를 쓰지만,
PDF와 달리 이미지는 "페이지"라는 개념이 없어서 훨씬 단순하다 — 전체 내용을
한 장의 이미지에 그대로 담기만 하면 된다(페이지 나누기/머리글/바닥글 없음).
보고서 등 다른 문서에 계산 결과를 캡처해서 붙여넣고 싶을 때, PDF를 열어
스크린샷 찍는 것보다 바로 쓰기 편하다.
"""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QGraphicsScene

#: 이미지 가장자리에 둘 여백(씬 좌표 기준 px, scale 배율 적용 전). 내용이 이미지
#: 경계에 딱 붙어 잘려 보이지 않도록 살짝 띄운다.
DEFAULT_MARGIN_PX = 20.0
#: 화면 그대로(1배)보다 또렷하게 보이도록 기본으로 2배 확대해서 내보낸다.
DEFAULT_SCALE = 2.0


def export_to_png(
    scene: QGraphicsScene,
    file_path: str,
    scale: float = DEFAULT_SCALE,
    margin_px: float = DEFAULT_MARGIN_PX,
) -> bool:
    """
    씬의 내용을 PNG 이미지로 내보낸다.

    Args:
        scene: 내보낼 캔버스 씬 (DocumentScene). 선택된 블록의 점선 테두리 등이
               찍히지 않도록, 호출하는 쪽에서 미리 scene.clearSelection()을
               해두는 걸 권장한다.
        file_path: 저장할 .png 파일 경로
        scale: 확대 배율. 기본 2배 — 화면 그대로(1배)보다 인쇄/확대해도
               덜 흐려 보인다.
        margin_px: 내용 가장자리에 둘 여백(씬 좌표 기준, scale 적용 전)

    Returns:
        성공하면 True. 캔버스에 블록이 하나도 없으면(내보낼 내용이 없으면)
        또는 파일 저장에 실패하면 False.
    """
    content_rect = scene.itemsBoundingRect()
    if content_rect.isEmpty():
        return False

    padded_rect = content_rect.adjusted(-margin_px, -margin_px, margin_px, margin_px)
    image_size = QSize(
        max(1, round(padded_rect.width() * scale)),
        max(1, round(padded_rect.height() * scale)),
    )

    image = QImage(image_size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    target_rect = QRectF(0, 0, image_size.width(), image_size.height())
    scene.render(painter, target_rect, padded_rect, Qt.AspectRatioMode.KeepAspectRatio)
    painter.end()

    return image.save(file_path, "PNG")
