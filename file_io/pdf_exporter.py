"""
캔버스 내용을 PDF로 내보내거나 인쇄한다.

QGraphicsScene을 그대로 QPdfWriter/QPrinter(둘 다 QPagedPaintDevice 계열이라
API가 거의 같다)에 렌더링하는 방식을 쓴다. 수식(mathtext 이미지), 텍스트
서식, 이미지가 이미 각 블록의 paint()에 구현되어 있으므로, 이 방식을 쓰면
화면 캔버스와 PDF/인쇄 결과가 항상 똑같이 보이는 게 저절로 보장된다 —
ReportLab으로 블록마다 그리기 로직을 새로 만들면 화면 렌더링과 따로 놀
위험이 있어, 계획서 기술스택 표의 "Qt 자체 QPrinter" 쪽을 택했다.

A4 용지, 여백, 콘텐츠가 한 페이지보다 길면 여러 페이지로 나누기, 머리글
(제목+날짜)/바닥글(페이지 번호)을 처리한다 — 이 페이지 나누기/배율/머리글·
바닥글 로직(_render_scene_to_paged_device)은 PDF 내보내기(export_to_pdf)와
인쇄(print_scene)가 그대로 공유한다. 대상 장치만 QPdfWriter냐 QPrinter냐가
다를 뿐, "씬을 A4 여러 페이지로 나눠 그린다"는 본질은 같기 때문이다.
"""

import math
from datetime import date
from typing import Union

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QGraphicsScene

#: export_to_pdf()/print_scene()이 공통으로 그리는 대상 장치 — 둘 다
#: QPagedPaintDevice의 하위 클래스라 pageLayout()/resolution()/newPage()를
#: 똑같이 지원한다.
_PagedDevice = Union[QPdfWriter, QPrinter]

#: 기본 용지 여백(mm). export_to_pdf()의 margin_mm 인자로 바꿀 수 있다.
DEFAULT_MARGIN_MM = 20.0
#: 머리글/바닥글 영역 높이(mm) — 이 영역은 본문(씬 렌더링) 배치에서 제외된다.
HEADER_HEIGHT_MM = 12.0
FOOTER_HEIGHT_MM = 10.0
#: 화면과 비슷한 크기 감각을 유지하기 위한 렌더링 해상도(dpi).
RESOLUTION_DPI = 96


def export_to_pdf(
    scene: QGraphicsScene,
    file_path: str,
    title: str = "",
    margin_mm: float = DEFAULT_MARGIN_MM,
    show_header_footer: bool = False,
) -> bool:
    """
    씬의 내용을 A4 PDF로 내보낸다.

    Args:
        scene: 내보낼 캔버스 씬 (DocumentScene). 선택된 블록의 점선 테두리 등이
               찍히지 않도록, 호출하는 쪽에서 미리 scene.clearSelection()을
               해두는 걸 권장한다.
        file_path: 저장할 .pdf 파일 경로
        title: 머리글에 표시할 문서 제목 (비어 있으면 "EngCalc 문서")
        margin_mm: 용지 여백(mm), 네 방향 동일하게 적용
        show_header_footer: 머리글(제목+날짜)/바닥글(페이지 번호) + 구분선을
            찍을지. 기본은 꺼짐 — 나중에 이 머리글/바닥글을 사용자가 직접
            구성하는 기능이 따로 생길 예정이라, 그 전까지는 내보내기 결과가
            화면 내용만 깔끔하게 담도록 기본값을 off로 둔다.

    Returns:
        성공하면 True. 캔버스에 블록이 하나도 없으면(내보낼 내용이 없으면) False.
    """
    content_rect = scene.itemsBoundingRect()
    if content_rect.isEmpty():
        return False

    writer = QPdfWriter(file_path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(margin_mm, margin_mm, margin_mm, margin_mm), QPageLayout.Unit.Millimeter)
    writer.setResolution(RESOLUTION_DPI)

    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _render_scene_to_paged_device(scene, writer, painter, title, show_header_footer)
    painter.end()
    return True


def print_scene(scene: QGraphicsScene, printer: QPrinter, title: str = "", show_header_footer: bool = False) -> bool:
    """
    씬의 내용을 이미 인쇄 대화상자를 통과한 QPrinter에 인쇄한다.

    export_to_pdf()와 페이지 나누기/배율/머리글·바닥글 로직을 그대로
    공유한다 — 대상 장치만 QPdfWriter 대신 QPrinter일 뿐이다.

    Args:
        scene: 인쇄할 캔버스 씬 (DocumentScene). export_to_pdf()와 마찬가지로,
               호출하는 쪽에서 미리 scene.clearSelection()을 해두는 걸 권장한다.
        printer: 용지 크기/여백/프린터가 이미 정해진 QPrinter (보통 QPrintDialog를
                 통과한 뒤). 그 설정을 그대로 존중해서 그린다 — 여기서 임의로
                 A4나 여백을 강제하지 않는다(사용자가 대화상자에서 고른 값 우선).
        title: 머리글에 표시할 문서 제목 (비어 있으면 "EngCalc 문서")
        show_header_footer: export_to_pdf()와 동일 — 기본은 꺼짐.

    Returns:
        성공하면 True. 캔버스에 블록이 하나도 없으면(인쇄할 내용이 없으면) False.
    """
    content_rect = scene.itemsBoundingRect()
    if content_rect.isEmpty():
        return False

    painter = QPainter(printer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _render_scene_to_paged_device(scene, printer, painter, title, show_header_footer)
    painter.end()
    return True


def _render_scene_to_paged_device(
    scene: QGraphicsScene, writer: _PagedDevice, painter: QPainter, title: str, show_header_footer: bool
) -> None:
    """
    이미 페이지 크기/여백이 정해지고 painter가 시작된 장치(writer)에, 씬을
    여러 페이지로 나눠 그린다. export_to_pdf()/print_scene() 공용 핵심 로직.
    """
    content_rect = scene.itemsBoundingRect()
    page_rect = QRectF(writer.pageLayout().paintRectPixels(writer.resolution()))
    if show_header_footer:
        header_h = _mm_to_px(HEADER_HEIGHT_MM, writer.resolution())
        footer_h = _mm_to_px(FOOTER_HEIGHT_MM, writer.resolution())
    else:
        header_h = 0.0
        footer_h = 0.0
    body_top = header_h
    body_height = page_rect.height() - header_h - footer_h
    body_width = page_rect.width()

    # 씬 콘텐츠가 본문 폭보다 넓을 때만 줄인다 — 화면보다 작은 내용을 억지로
    # 페이지 폭에 맞춰 키우면(예: 한 줄짜리 짧은 블록) 글자가 비정상적으로
    # 커 보인다("비율이 이상해 보인다"는 사용자 피드백의 원인이었다).
    scale = min(1.0, body_width / content_rect.width()) if content_rect.width() > 0 else 1.0
    # 한 페이지의 본문 영역에 들어가는 만큼을, 씬 좌표 기준 높이로 환산.
    band_height_scene = body_height / scale if scale > 0 else content_rect.height()
    page_count = max(1, math.ceil(content_rect.height() / band_height_scene))

    display_title = title or "EngCalc 문서"
    for page_index in range(page_count):
        if page_index > 0:
            writer.newPage()

        band_top = content_rect.top() + page_index * band_height_scene
        band_height = min(band_height_scene, content_rect.bottom() - band_top)
        source_rect = QRectF(content_rect.left(), band_top, content_rect.width(), band_height)
        # target_rect도 source와 같은 배율(scale)로 맞춰야 한다 — 폭을 항상
        # body_width로 고정해버리면, source/target 종횡비가 달라져서
        # KeepAspectRatio가 다시 확대해버리는(스케일 캡을 무력화하는) 결과가 된다.
        target_rect = QRectF(0, body_top, content_rect.width() * scale, band_height * scale)

        scene.render(painter, target_rect, source_rect, Qt.AspectRatioMode.KeepAspectRatio)
        if show_header_footer:
            _draw_header(painter, page_rect, header_h, display_title)
            _draw_footer(painter, page_rect, footer_h, page_index + 1, page_count)


def _mm_to_px(value_mm: float, dpi: int) -> float:
    """mm 단위를 주어진 해상도(dpi) 기준 픽셀 단위로 변환한다 (1인치 = 25.4mm)."""
    return value_mm / 25.4 * dpi


def _draw_header(painter: QPainter, page_rect: QRectF, header_h: float, title: str) -> None:
    """머리글: 왼쪽에 문서 제목, 오른쪽에 오늘 날짜, 아래에 구분선."""
    painter.save()
    header_rect = QRectF(0, 0, page_rect.width(), header_h)

    title_font = QFont()
    title_font.setPointSize(12)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(header_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

    date_font = QFont()
    date_font.setPointSize(9)
    painter.setFont(date_font)
    painter.drawText(
        header_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, date.today().isoformat()
    )

    painter.drawLine(0, round(header_h), round(page_rect.width()), round(header_h))
    painter.restore()


def _draw_footer(painter: QPainter, page_rect: QRectF, footer_h: float, page_number: int, total_pages: int) -> None:
    """바닥글: 위에 구분선, 가운데에 "N / 전체" 페이지 번호."""
    painter.save()
    footer_top = page_rect.height() - footer_h
    footer_rect = QRectF(0, footer_top, page_rect.width(), footer_h)

    font = QFont()
    font.setPointSize(9)
    painter.setFont(font)

    painter.drawLine(0, round(footer_top), round(page_rect.width()), round(footer_top))
    painter.drawText(footer_rect, Qt.AlignmentFlag.AlignCenter, f"{page_number} / {total_pages}")
    painter.restore()
