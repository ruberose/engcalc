"""file_io/pdf_exporter.py 단위 테스트."""

import os
import tempfile

from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication

import file_io.pdf_exporter as pdf_exporter_module
from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene
from file_io.pdf_exporter import export_to_pdf, print_scene

_app = QApplication.instance() or QApplication([])


def _pdf_backed_printer(file_path: str) -> QPrinter:
    """
    실제 프린터/대화상자 없이 print_scene()을 검증하기 위한 트릭.

    QPrinter는 물리 프린터뿐 아니라 "PDF 파일로 출력"도 표준으로 지원한다
    (많은 OS의 "PDF로 인쇄" 옵션과 같은 경로) — outputFormat을 PdfFormat으로
    돌려서, 실제 프린터 없이도 print_scene()이 만든 결과물을 파일로 받아
    검증할 수 있다.
    """
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(file_path)
    return printer


def test_export_creates_valid_pdf_file():
    """블록이 있는 문서를 내보내면 진짜 PDF 파일이 생겨야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(10, 10))
    block.set_text("1. 설계조건")
    scene.addItem(block)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "output.pdf")
        result = export_to_pdf(scene, file_path, title="테스트 문서")

        assert result is True
        assert os.path.exists(file_path)
        assert os.path.getsize(file_path) > 0

        with open(file_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"


def test_export_empty_scene_returns_false():
    """블록이 하나도 없는 빈 캔버스는 내보낼 게 없으므로 False를 돌려주고 파일을 만들지 않는다."""
    scene = DocumentScene()

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "empty.pdf")
        result = export_to_pdf(scene, file_path)

        assert result is False
        assert not os.path.exists(file_path)


def test_export_multi_page_for_tall_content():
    """세로로 긴 문서는 여러 페이지로 나뉘어야 한다."""
    scene = DocumentScene()
    # 블록을 세로로 아주 넓게 퍼뜨려서 한 페이지에 다 안 들어가게 만든다.
    for i in range(20):
        block = TextBlock(position=(10, i * 400))
        block.set_text(f"항목 {i}")
        scene.addItem(block)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "long.pdf")
        result = export_to_pdf(scene, file_path)

        assert result is True
        # 정확한 페이지 수는 PDF 파서 없이 확인하기 어려우니, 대신 파일 크기로
        # "페이지가 여러 장 만들어져서 한 페이지짜리보다 훨씬 크다"는 것만 확인한다.
        single_page_scene = DocumentScene()
        single_block = TextBlock(position=(10, 10))
        single_block.set_text("항목 0")
        single_page_scene.addItem(single_block)
        single_page_path = os.path.join(tmp_dir, "short.pdf")
        export_to_pdf(single_page_scene, single_page_path)

        assert os.path.getsize(file_path) > os.path.getsize(single_page_path)


def test_export_respects_grid_visibility_toggle():
    """set_grid_visible(False)로 꺼둔 상태에서 내보내도 다시 True로 잘 복구될 수 있어야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(10, 10))
    block.set_text("hello")
    scene.addItem(block)

    scene.set_grid_visible(False)
    assert scene._grid_visible is False

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "output.pdf")
        export_to_pdf(scene, file_path)

    scene.set_grid_visible(True)
    assert scene._grid_visible is True


def test_export_does_not_enlarge_content_narrower_than_page():
    """
    본문 폭보다 좁은 내용은 확대하지 않고 화면 그대로의 크기로 찍혀야 한다.

    사용자 피드백: "asdfasdfsdf" 한 줄짜리 블록을 PDF로 내보냈더니 글자가
    페이지 폭에 맞춰 비정상적으로 커져서 나왔다("비율이 이상하다") — 좁은
    한 줄짜리 씬을 억지로 페이지 폭까지 늘려 그리던 게 원인이었다.
    """
    scene = DocumentScene()
    block = TextBlock(position=(10, 10))
    block.set_text("a")  # 페이지 폭보다 훨씬 좁은 내용
    scene.addItem(block)

    captured: list[tuple] = []
    original_render = scene.render

    def spy_render(painter, target, source, *args, **kwargs):
        captured.append((target, source))
        return original_render(painter, target, source, *args, **kwargs)

    scene.render = spy_render

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "narrow.pdf")
        export_to_pdf(scene, file_path)

    assert len(captured) == 1
    target, source = captured[0]
    # 확대됐다면 target 너비가 source 너비(씬 좌표 기준 내용 너비)보다 훨씬
    # 컸을 것이다 — 확대하지 않았으면 거의 같아야 한다(scale == 1).
    assert abs(target.width() - source.width()) < 1e-6


def test_export_clips_content_wider_than_page_instead_of_shrinking():
    """
    내용이 본문 폭보다 넓으면 줄이지 않고 그냥 잘린다(다음 페이지로 넘기지 않음).

    사용자 피드백: "실제 출력물과 똑같이 프로그램에서 써져야 되지 않겠어?" —
    콘텐츠 폭에 맞춰 배율을 조정하던 예전 방식은, 문서 전체 콘텐츠 폭에
    따라 글자 크기가 매번 달라져서 화면과 다르게(예측 불가능하게) 찍혔다.
    이제는 항상 1:1로 찍고, 폭 초과분은 그냥 잘려서 두 번째 "폭 페이지"가
    생기지 않는다 — target/source 크기가 항상 똑같아야(스케일 없음) 한다.
    """
    scene = DocumentScene()
    wide_block = TextBlock(position=(0, 0))
    wide_block.set_text("아주 긴 텍스트 " * 40)  # 페이지 폭보다 훨씬 넓게
    scene.addItem(wide_block)

    captured: list[tuple] = []
    original_render = scene.render

    def spy_render(painter, target, source, *args, **kwargs):
        captured.append((target, source))
        return original_render(painter, target, source, *args, **kwargs)

    scene.render = spy_render

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "wide.pdf")
        export_to_pdf(scene, file_path)

    assert captured
    target, source = captured[0]
    assert abs(target.width() - source.width()) < 1e-6  # 스케일 없음(1:1)
    assert source.width() < scene.itemsBoundingRect().width()  # 폭 초과분은 잘림


def test_header_footer_off_by_default():
    """머리글/바닥글은 기본적으로 그리지 않아야 한다(나중에 별도 기능으로 추가 예정)."""
    calls: list[str] = []
    original_header = pdf_exporter_module._draw_header
    original_footer = pdf_exporter_module._draw_footer
    pdf_exporter_module._draw_header = lambda *a, **kw: calls.append("header")
    pdf_exporter_module._draw_footer = lambda *a, **kw: calls.append("footer")
    try:
        scene = DocumentScene()
        block = TextBlock(position=(10, 10))
        block.set_text("머리글 없음 확인")
        scene.addItem(block)

        with tempfile.TemporaryDirectory() as tmp_dir:
            export_to_pdf(scene, os.path.join(tmp_dir, "no_header.pdf"))
    finally:
        pdf_exporter_module._draw_header = original_header
        pdf_exporter_module._draw_footer = original_footer

    assert calls == []


def test_header_footer_drawn_when_requested():
    """show_header_footer=True로 명시하면 머리글/바닥글을 그려야 한다."""
    calls: list[str] = []
    original_header = pdf_exporter_module._draw_header
    original_footer = pdf_exporter_module._draw_footer
    pdf_exporter_module._draw_header = lambda *a, **kw: calls.append("header")
    pdf_exporter_module._draw_footer = lambda *a, **kw: calls.append("footer")
    try:
        scene = DocumentScene()
        block = TextBlock(position=(10, 10))
        block.set_text("머리글 있음 확인")
        scene.addItem(block)

        with tempfile.TemporaryDirectory() as tmp_dir:
            export_to_pdf(scene, os.path.join(tmp_dir, "with_header.pdf"), show_header_footer=True)
    finally:
        pdf_exporter_module._draw_header = original_header
        pdf_exporter_module._draw_footer = original_footer

    assert calls == ["header", "footer"]


# --- print_scene() (export_to_pdf()와 페이지 렌더링 로직을 공유) ---


def test_print_scene_produces_output():
    """인쇄할 내용이 있으면 True를 돌려주고 실제로 뭔가 그려져야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(10, 10))
    block.set_text("인쇄 테스트")
    scene.addItem(block)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "printed.pdf")
        printer = _pdf_backed_printer(file_path)
        result = print_scene(scene, printer, title="테스트 문서")

        assert result is True
        assert os.path.exists(file_path)
        assert os.path.getsize(file_path) > 0


def test_print_scene_empty_scene_returns_false():
    """인쇄할 블록이 하나도 없으면 False를 돌려주고 아무 것도 만들지 않는다."""
    scene = DocumentScene()

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "empty.pdf")
        printer = _pdf_backed_printer(file_path)
        result = print_scene(scene, printer)

        assert result is False


def test_print_scene_respects_printer_page_layout():
    """export_to_pdf()처럼 강제로 A4/여백을 정하지 않고, printer에 이미 설정된 값을 그대로 써야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(10, 10))
    block.set_text("용지 설정 확인")
    scene.addItem(block)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "letter.pdf")
        printer = _pdf_backed_printer(file_path)
        from PySide6.QtGui import QPageSize

        printer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))

        result = print_scene(scene, printer, title="Letter 용지")

        assert result is True
        assert printer.pageLayout().pageSize().id() == QPageSize.PageSizeId.Letter
