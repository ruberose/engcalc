"""
EngCalc 메인 윈도우 모듈.

앱의 최상위 창(QMainWindow)을 정의한다.
실제 캔버스 동작(격자, 블록 생성/편집)은 canvas/, blocks/ 모듈이 담당하고,
파일 저장/불러오기의 실제 JSON 처리는 file_io/file_manager.py가 담당한다.
이 파일은 메뉴바·상태바·창 제목 등 "창" 자체의 상태만 관리한다.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import QDockWidget, QFileDialog, QGraphicsTextItem, QMainWindow, QMenu, QMessageBox

from app.settings import add_recent_file, autosave_file_path, get_recent_files
from blocks.base_block import BaseBlock
from blocks.image_block import SUPPORTED_EXTENSIONS
from blocks.math_block import MathBlock
from canvas.document_scene import DocumentScene
from canvas.document_view import DocumentView
from file_io.file_manager import load_document, save_document
from file_io.pdf_exporter import export_to_pdf
from ui.find_dialog import FindDialog
from ui.help_dialog import HelpDialog
from ui.new_document_dialog import NewDocumentDialog
from ui.property_panel import PropertyPanel
from ui.variable_inspector import VariableInspector

#: QFileDialog에 보여줄 확장자 필터 문자열 (예: "*.png *.jpg *.jpeg *.bmp *.svg").
_IMAGE_FILE_FILTER = "이미지 파일 (" + " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS) + ")"

#: .engcalc 파일 관련 상수.
_FILE_EXTENSION = ".engcalc"
_FILE_FILTER = "EngCalc 문서 (*.engcalc)"
_DOCUMENT_VERSION = "1.0"
_DEFAULT_TITLE = "제목 없음"

#: 자동 저장 주기(밀리초). 이 주기마다 깨어나서 "저장 안 한 변경사항이
#: 있으면" 자동 저장한다(변경이 없으면 아무것도 안 씀).
_AUTOSAVE_INTERVAL_MS = 60_000


class MainWindow(QMainWindow):
    """
    EngCalc의 메인 윈도우.

    구조:
        메뉴바 (파일/편집/보기/도움말)
        중앙: DocumentView + DocumentScene (문서 캔버스)
        오른쪽: 속성 패널 / 변수 목록 패널 (탭으로 겹쳐 있음, 보기 메뉴에서 토글 가능)
        상태바

    사용 예:
        window = MainWindow()
        window.show()
    """

    def __init__(self) -> None:
        """메인 윈도우를 초기화하고 캔버스·메뉴바·상태바를 배치한다."""
        super().__init__()

        self.resize(1200, 800)

        # --- 현재 문서 상태 ---
        self._current_file_path: str | None = None
        self._created_at: str = datetime.now().isoformat()
        self._is_modified: bool = False
        self._recovered_from_autosave: bool = False  # 복구된 내용이면 "수정됨" 표시를 지우면 안 됨
        self._help_dialog: HelpDialog | None = None  # 도움말 창은 처음 열 때 한 번만 만든다
        self._find_dialog: FindDialog | None = None  # 찾기 창도 처음 열 때 한 번만 만든다

        # 메뉴의 "이미지 삽입"/"열기" 등이 self._scene/self._view를 참조하므로
        # 캔버스를 먼저 만들어야 한다. 사이드 패널(속성/변수 목록)도 씬이 있어야
        # 연결할 수 있으므로 그다음, 메뉴바는 "보기" 메뉴에서 패널을 토글하는
        # 액션을 넣어야 하니 맨 마지막에 만든다.
        self._create_canvas()
        self._create_side_panels()
        self._create_menu_bar()
        self.statusBar().showMessage(
            "준비됨 — 더블클릭: 수식 블록 추가 / Ctrl+더블클릭: 텍스트 블록 추가"
        )
        self._update_window_title()
        self._check_autosave_recovery()

        # 자동 저장 타이머. 주기적으로 깨어나서 "저장 안 한 변경사항이 있으면"만
        # 실제로 자동 저장 파일을 쓴다(_on_autosave_tick).
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(_AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._on_autosave_tick)
        self._autosave_timer.start()

        # QGraphicsScene.changed는 최초 화면이 그려질 때도 한 번 울린다(빈 캔버스를
        # 처음 페인트하는 것도 "변경"으로 잡히기 때문). 그걸 실제 사용자 수정으로
        # 오인하지 않도록, 이번 이벤트 루프 한 바퀴가 끝난 뒤에 플래그를 정리한다.
        QTimer.singleShot(0, self._reset_modified_flag)

    def _reset_modified_flag(self) -> None:
        """
        초기 렌더링으로 인해 잘못 켜진 "수정됨" 표시를 끈다.

        Note:
            자동 저장 내용을 복구한 직후라면 건너뛴다 — 복구된 내용은 아직
            실제 파일에 저장된 게 아니므로, "수정됨(*)" 표시가 그대로 남아
            사용자에게 저장을 유도해야 한다.
        """
        if self._recovered_from_autosave:
            return
        self._is_modified = False
        self._update_window_title()

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

        # QGraphicsScene.changed는 블록 추가/이동/편집 등 무엇이든 화면이 바뀌면
        # 울리는 Qt 내장 신호다. 블록 클래스마다 "수정됨" 신호를 따로 만드는 대신
        # 이걸 그대로 "수정 감지"에 활용한다 (선택만 해도 살짝 과민하게 반응할 수
        # 있지만, 실수로 저장 안 하고 닫는 것보다는 훨씬 안전한 쪽을 택함).
        self._scene.changed.connect(self._on_scene_changed)

    def _create_side_panels(self) -> None:
        """오른쪽에 속성 패널과 변수 목록 패널을 도킹 창으로 배치한다."""
        self._property_panel = PropertyPanel()
        self._property_dock = QDockWidget("속성", self)
        self._property_dock.setWidget(self._property_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._property_dock)

        self._variable_inspector = VariableInspector()
        self._variable_inspector.set_scene(self._scene)
        self._variable_inspector.block_activated.connect(self._on_variable_activated)
        self._variable_dock = QDockWidget("변수 목록", self)
        self._variable_dock.setWidget(self._variable_inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._variable_dock)

        # 같은 자리에 위아래로 쌓인 두 패널을 탭으로 겹쳐서, 필요할 때 골라 보게 한다.
        self.tabifyDockWidget(self._property_dock, self._variable_dock)
        self._property_dock.raise_()

        # 캔버스에서 블록을 클릭/선택 해제할 때마다 속성 패널이 그 블록을 보여주게 한다.
        self._scene.selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self) -> None:
        """캔버스 선택이 바뀌면 속성 패널에 반영한다 (블록 하나만 선택됐을 때만 표시)."""
        selected = [item for item in self._scene.selectedItems() if isinstance(item, BaseBlock)]
        self._property_panel.show_block(selected[0] if len(selected) == 1 else None)
        self._update_edit_menu_state()

    def _on_variable_activated(self, block: MathBlock) -> None:
        """변수 목록에서 항목을 더블클릭하면, 그 변수를 정의한 블록으로 캔버스를 이동한다."""
        self._view.centerOn(block)
        self._scene.clearSelection()
        block.setSelected(True)

    def _create_menu_bar(self) -> None:
        """
        상단 메뉴바를 구성한다.

        Note:
            편집/보기/도움말은 아직 구현 전이라(Undo 등은 1차 범위 밖) 빈 채로 두면
            "고장난 것"처럼 보이므로 비활성화된 안내 항목을 넣어둔다.
        """
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("파일(&F)")

        new_action = file_menu.addAction("새로 만들기(&N)")
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new_document)

        open_action = file_menu.addAction("열기(&O)...")
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_document)

        save_action = file_menu.addAction("저장(&S)")
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_document)

        save_as_action = file_menu.addAction("다른 이름으로 저장(&A)...")
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self._on_save_document_as)

        file_menu.addSeparator()
        self._recent_files_menu = file_menu.addMenu("최근 파일(&R)")
        self._rebuild_recent_files_menu()

        file_menu.addSeparator()
        insert_image_action = file_menu.addAction("이미지 삽입(&I)...")
        insert_image_action.triggered.connect(self._on_insert_image)

        file_menu.addSeparator()
        export_pdf_action = file_menu.addAction("PDF로 내보내기(&P)...")
        export_pdf_action.triggered.connect(self._on_export_pdf)

        edit_menu = menu_bar.addMenu("편집(&E)")

        self._undo_action = edit_menu.addAction("실행 취소(&U)")
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._on_undo)

        self._redo_action = edit_menu.addAction("다시 실행(&R)")
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.triggered.connect(self._on_redo)

        edit_menu.addSeparator()

        self._copy_action = edit_menu.addAction("복사(&C)")
        self._copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self._copy_action.triggered.connect(self._on_copy)

        self._paste_action = edit_menu.addAction("붙여넣기(&P)")
        self._paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self._paste_action.triggered.connect(self._on_paste)

        edit_menu.addSeparator()

        find_action = edit_menu.addAction("찾기(&F)...")
        find_action.setShortcut(QKeySequence.StandardKey.Find)
        find_action.triggered.connect(self._on_show_find)

        edit_menu.aboutToShow.connect(self._update_edit_menu_state)
        self._update_edit_menu_state()

        view_menu = menu_bar.addMenu("보기(&V)")
        view_menu.addAction(self._property_dock.toggleViewAction())
        view_menu.addAction(self._variable_dock.toggleViewAction())

        help_menu = menu_bar.addMenu("도움말(&H)")
        help_action = help_menu.addAction("EngCalc 사용법(&U)...")
        help_action.setShortcut(QKeySequence.StandardKey.HelpContents)
        help_action.triggered.connect(self._on_show_help)

    def _add_placeholder(self, menu: QMenu) -> None:
        """메뉴에 "(구현 예정)" 비활성 항목을 하나 추가한다."""
        placeholder = menu.addAction("(구현 예정)")
        placeholder.setEnabled(False)

    # --- 편집: 실행취소 / 다시실행 / 복사 / 붙여넣기 ---

    def _is_editing_text(self) -> bool:
        """
        지금 어떤 블록이든 텍스트 편집 중인지 확인한다.

        Note:
            MathBlock/TextBlock 자신도 ItemIsFocusable이라, 그냥 클릭만 해도
            (편집 모드로 들어가지 않아도) scene.focusItem()이 그 블록 자신이 될 수
            있다 — 그래서 "focusItem이 있냐 없냐"만으로는 편집 중인지 판단할 수
            없다. 실제 편집기(_InlineTextEditor/_UnitEditor)는 모두 QGraphicsTextItem
            서브클래스이고 블록 자신(BaseBlock)은 QGraphicsItem이라 겹치지 않으므로,
            focusItem이 QGraphicsTextItem인지로 정확히 구분한다.
        """
        return isinstance(self._scene.focusItem(), QGraphicsTextItem)

    def _on_undo(self) -> None:
        """
        실행취소 메뉴/단축키(Ctrl+Z) 처리.

        Note:
            블록을 편집 중일 때는 Ctrl+Z가 편집기 자체의 텍스트 실행취소로 쓰이는 게
            자연스러우므로, 문서 단위 실행취소는 편집 중이 아닐 때만 동작한다.
        """
        if self._is_editing_text():
            return
        self._scene.undo()
        self._update_edit_menu_state()

    def _on_redo(self) -> None:
        """다시실행 메뉴/단축키(Ctrl+Y) 처리. 편집 중일 때는 무시한다(_on_undo와 같은 이유)."""
        if self._is_editing_text():
            return
        self._scene.redo()
        self._update_edit_menu_state()

    def _on_copy(self) -> None:
        """
        복사 메뉴/단축키(Ctrl+C) 처리. 편집 중일 때는 무시한다(_on_undo와 같은 이유).

        Note:
            복사는 화면을 바꾸지 않아 scene.changed가 안 울리므로, 붙여넣기 항목의
            활성 상태(can_paste())를 반영하려면 여기서 직접 갱신해야 한다.
        """
        if self._is_editing_text():
            return
        self._scene.copy_selected_blocks()
        self._update_edit_menu_state()

    def _on_paste(self) -> None:
        """붙여넣기 메뉴/단축키(Ctrl+V) 처리. 편집 중일 때는 무시한다(_on_undo와 같은 이유)."""
        if self._is_editing_text():
            return
        pasted = self._scene.paste_blocks()
        if pasted:
            self.statusBar().showMessage(f"{len(pasted)}개 블록을 붙여넣었습니다", 2000)
        self._update_edit_menu_state()

    def _update_edit_menu_state(self) -> None:
        """편집 메뉴가 열릴 때마다(aboutToShow) 각 항목의 활성/비활성 상태를 갱신한다."""
        self._undo_action.setEnabled(self._scene.can_undo())
        self._redo_action.setEnabled(self._scene.can_redo())
        self._copy_action.setEnabled(bool(self._scene.selectedItems()))
        self._paste_action.setEnabled(self._scene.can_paste())

    # --- 수정 감지 / 창 제목 ---

    def _on_scene_changed(self, _regions: list) -> None:
        """캔버스에 뭔가 변화가 생기면 "수정됨" 표시를 하고, 속성 패널 값도 최신으로 맞춘다."""
        if not self._is_modified:
            self._is_modified = True
            self._update_window_title()

        # 선택된 블록을 드래그해서 옮기는 중에도 속성 패널의 X/Y가 따라가도록 갱신한다.
        current = self._property_panel.current_block()
        if current is not None:
            self._property_panel.show_block(current)

        # 편집 메뉴 항목(실행취소/다시실행/붙여넣기)의 활성 상태를 실시간으로 맞춘다.
        # aboutToShow에서만 갱신하면, 메뉴를 한 번도 열지 않은 채 Ctrl+Z 같은
        # 단축키를 누를 때 액션이 비활성 상태로 굳어 있어 동작하지 않는 문제가
        # 있었다(비활성 QAction은 단축키로도 trigger되지 않음) — 버그체크 중 발견.
        self._update_edit_menu_state()

    def _update_window_title(self) -> None:
        """창 제목을 "[*]파일명 - EngCalc" 형태로 갱신한다."""
        name = Path(self._current_file_path).stem if self._current_file_path else _DEFAULT_TITLE
        mark = "*" if self._is_modified else ""
        self.setWindowTitle(f"{mark}{name} - EngCalc")

    # --- 자동 저장 / 비정상 종료 복구 ---

    def _check_autosave_recovery(self) -> None:
        """
        시작할 때 자동 저장 파일이 남아있으면 복구할지 물어본다.

        Note:
            정상적으로 저장/새 문서/파일 열기/종료를 하면 _clear_autosave()가
            이 파일을 지운다. 그러니 다음 실행 때 이 파일이 남아있다는 것
            자체가 "지난번에 비정상 종료됐다"는 신호다.
        """
        path = autosave_file_path()
        if not Path(path).exists():
            return

        try:
            data = load_document(path)
            blocks = data.get("blocks", [])
            if not isinstance(blocks, list):
                raise ValueError("blocks가 리스트가 아님")
        except (OSError, json.JSONDecodeError, ValueError):
            Path(path).unlink(missing_ok=True)  # 손상된 자동 저장 파일은 조용히 버림
            return

        original_path = data.get("metadata", {}).get("original_file_path")
        label = Path(original_path).stem if original_path else _DEFAULT_TITLE
        choice = QMessageBox.question(
            self,
            "복구할 내용이 있습니다",
            f'이전에 비정상적으로 종료된 것 같습니다.\n자동 저장된 내용("{label}")을 복구할까요?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if choice != QMessageBox.StandardButton.Yes:
            Path(path).unlink(missing_ok=True)
            return

        metadata = data.get("metadata", {})
        self._scene.set_document_format(
            metadata.get("document_format", "freeform"), metadata.get("paper_size", "A4")
        )
        self._scene.load_blocks_list(blocks)
        self._current_file_path = original_path
        self._created_at = metadata.get("created", datetime.now().isoformat())
        self._recovered_from_autosave = True
        self._is_modified = True
        self._update_window_title()
        self.statusBar().showMessage("자동 저장된 내용을 복구했습니다 — 확인 후 저장해주세요", 5000)

    def _on_autosave_tick(self) -> None:
        """자동 저장 타이머가 주기적으로 부른다. 저장 안 한 변경사항이 있을 때만 실제로 쓴다."""
        if self._is_modified:
            self._write_autosave()

    def _write_autosave(self) -> None:
        """지금 문서 상태를 자동 저장 파일에 써둔다 (사용자가 실제로 저장하는 파일과는 별개)."""
        data: dict[str, Any] = {
            "version": _DOCUMENT_VERSION,
            "metadata": {
                "title": Path(self._current_file_path).stem if self._current_file_path else _DEFAULT_TITLE,
                "created": self._created_at,
                "modified": datetime.now().isoformat(),
                # 복구했을 때 원래 파일로 되돌려 저장할 수 있도록 원본 경로도 같이 적어둔다.
                "original_file_path": self._current_file_path,
                "document_format": self._scene.document_format(),
                "paper_size": self._scene.paper_size(),
            },
            "blocks": self._scene.to_blocks_list(),
        }
        try:
            save_document(data, autosave_file_path())
        except OSError:
            pass  # 자동 저장 실패는 조용히 넘어간다 — 다음 주기에 다시 시도됨

    def _clear_autosave(self) -> None:
        """자동 저장 파일을 지운다. 정상적으로 저장/새 문서/열기/종료했을 때 부른다."""
        Path(autosave_file_path()).unlink(missing_ok=True)
        self._recovered_from_autosave = False

    # --- 새로 만들기 / 열기 / 저장 ---

    def _on_new_document(self) -> None:
        """
        새 문서의 형식(자유 캔버스/용지)을 물어본 뒤, 현재 문서를 비우고 새 문서를 시작한다.

        저장 안 한 변경사항이 있으면 먼저 물어보고, 형식 선택 대화상자에서
        취소를 누르면 지금 문서를 그대로 두고 아무 것도 하지 않는다.
        """
        if not self._confirm_discard_changes():
            return
        dialog = NewDocumentDialog(self)
        if dialog.exec() != NewDocumentDialog.DialogCode.Accepted:
            return
        document_format, paper_size = dialog.result_format()

        self._scene.load_blocks_list([])
        self._scene.set_document_format(document_format, paper_size)
        self._current_file_path = None
        self._created_at = datetime.now().isoformat()
        self._is_modified = False
        self._clear_autosave()  # 이전 문서의 자동 저장 내용은 더 이상 의미가 없음
        self._update_window_title()
        self.statusBar().showMessage("새 문서", 3000)
        # load_blocks_list()가 발생시키는 scene.changed도 "진짜 수정"이 아니므로,
        # 그 신호가 다 가라앉은 뒤 한 번 더 정리한다 (__init__의 같은 처리와 동일한 이유).
        QTimer.singleShot(0, self._reset_modified_flag)

    def _on_open_document(self) -> None:
        """파일 선택 대화상자를 띄워 .engcalc 파일을 연다."""
        if not self._confirm_discard_changes():
            return
        file_path, _selected_filter = QFileDialog.getOpenFileName(self, "파일 열기", "", _FILE_FILTER)
        if not file_path:
            return
        self._load_from_path(file_path)

    def _load_from_path(self, file_path: str) -> None:
        """지정한 경로의 .engcalc 파일을 읽어 캔버스에 복원한다."""
        try:
            data = load_document(file_path)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "파일 열기 실패", f"파일을 열 수 없습니다:\n{file_path}\n\n{exc}")
            return

        try:
            self._scene.load_blocks_list(data.get("blocks", []))
        except (AttributeError, TypeError) as exc:
            # DocumentScene.load_blocks_list()가 블록 하나하나의 손상은 이미 알아서
            # 건너뛰지만(KeyError/ValueError/TypeError), "blocks"가 아예 리스트가
            # 아니라거나 하는 파일 구조 자체의 문제는 여기서 한 번 더 막는다 —
            # 어떤 경우에도 손상된 파일 하나 때문에 앱이 죽으면 안 된다(코드 규칙 4.4).
            QMessageBox.critical(self, "파일 열기 실패", f"파일 형식이 올바르지 않습니다:\n{file_path}\n\n{exc}")
            return

        metadata = data.get("metadata", {})
        self._scene.set_document_format(
            metadata.get("document_format", "freeform"), metadata.get("paper_size", "A4")
        )
        self._created_at = metadata.get("created", datetime.now().isoformat())
        self._current_file_path = file_path
        self._is_modified = False
        self._clear_autosave()  # 방금 진짜 파일을 열었으니 이전 자동 저장 내용은 의미가 없음

        add_recent_file(file_path)
        self._rebuild_recent_files_menu()
        self._update_window_title()
        self.statusBar().showMessage(f"열었습니다: {file_path}", 3000)
        QTimer.singleShot(0, self._reset_modified_flag)

    def _on_save_document(self) -> bool:
        """현재 파일에 저장한다. 아직 저장한 적 없으면 "다른 이름으로 저장"으로 넘어간다."""
        if self._current_file_path is None:
            return self._on_save_document_as()
        return self._save_to_path(self._current_file_path)

    def _on_save_document_as(self) -> bool:
        """파일 선택 대화상자를 띄워 새 경로에 저장한다."""
        file_path, _selected_filter = QFileDialog.getSaveFileName(self, "다른 이름으로 저장", "", _FILE_FILTER)
        if not file_path:
            return False
        if not file_path.lower().endswith(_FILE_EXTENSION):
            file_path += _FILE_EXTENSION
        return self._save_to_path(file_path)

    def _save_to_path(self, file_path: str) -> bool:
        """문서를 dict로 만들어 지정한 경로에 저장한다."""
        now = datetime.now().isoformat()
        data: dict[str, Any] = {
            "version": _DOCUMENT_VERSION,
            "metadata": {
                "title": Path(file_path).stem,
                "author": "",
                "created": self._created_at,
                "modified": now,
                "document_format": self._scene.document_format(),
                "paper_size": self._scene.paper_size(),
            },
            "blocks": self._scene.to_blocks_list(),
        }

        try:
            save_document(data, file_path)
        except OSError as exc:
            QMessageBox.critical(self, "저장 실패", f"파일을 저장할 수 없습니다:\n{file_path}\n\n{exc}")
            return False

        self._current_file_path = file_path
        self._is_modified = False
        self._clear_autosave()  # 진짜 파일에 저장했으니 자동 저장 내용은 더 이상 필요 없음
        add_recent_file(file_path)
        self._rebuild_recent_files_menu()
        self._update_window_title()
        self.statusBar().showMessage(f"저장했습니다: {file_path}", 3000)
        return True

    def _confirm_discard_changes(self) -> bool:
        """
        저장 안 된 변경사항이 있으면 저장할지 물어본다.

        Returns:
            계속 진행해도 되면 True (저장 완료했거나, "버리기" 선택했거나, 애초에 변경사항 없음).
            "취소"를 선택했으면 False (호출한 쪽은 하려던 동작을 멈춰야 함).
        """
        if not self._is_modified:
            return True

        choice = QMessageBox.question(
            self,
            "저장하지 않은 변경사항",
            "저장하지 않은 변경사항이 있습니다. 저장할까요?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            return self._on_save_document()
        return choice == QMessageBox.StandardButton.Discard

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """창을 닫으려 할 때, 저장 안 한 변경사항이 있으면 먼저 확인한다."""
        if self._confirm_discard_changes():
            self._clear_autosave()  # 정상적으로 닫는 것이므로 다음 실행 때 복구할 필요 없음
            event.accept()
        else:
            event.ignore()

    # --- 최근 파일 ---

    def _rebuild_recent_files_menu(self) -> None:
        """"최근 파일" 하위 메뉴를 현재 설정값 기준으로 다시 그린다."""
        self._recent_files_menu.clear()
        recent = get_recent_files()

        if not recent:
            self._add_placeholder(self._recent_files_menu)
            return

        for file_path in recent:
            action = self._recent_files_menu.addAction(file_path)
            action.triggered.connect(lambda checked=False, path=file_path: self._open_recent_file(path))

    def _open_recent_file(self, file_path: str) -> None:
        """"최근 파일" 메뉴에서 항목을 선택했을 때 그 파일을 연다."""
        if not self._confirm_discard_changes():
            return
        if not Path(file_path).exists():
            QMessageBox.warning(self, "파일 없음", f"파일을 찾을 수 없습니다:\n{file_path}")
            return
        self._load_from_path(file_path)

    # --- 이미지 삽입 ---

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

    # --- PDF 내보내기 ---

    def _on_export_pdf(self) -> None:
        """
        파일 선택 대화상자를 띄워 현재 문서를 PDF로 내보낸다.

        Note:
            선택된 블록이 있으면 점선 테두리/크기조절 손잡이까지 PDF에 찍히므로
            내보내기 전에 선택을 해제한다. 격자 배경도 인쇄용으로는 지저분해
            보이므로 내보내는 동안만 꺼둔다(scene.set_grid_visible).
        """
        default_name = Path(self._current_file_path).stem if self._current_file_path else _DEFAULT_TITLE
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self, "PDF로 내보내기", f"{default_name}.pdf", "PDF 파일 (*.pdf)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        self._scene.clearSelection()
        self._scene.set_grid_visible(False)
        try:
            exported = export_to_pdf(self._scene, file_path, title=default_name)
        except OSError as exc:
            QMessageBox.critical(self, "PDF 내보내기 실패", f"PDF를 저장할 수 없습니다:\n{file_path}\n\n{exc}")
            return
        finally:
            self._scene.set_grid_visible(True)

        if exported:
            self.statusBar().showMessage(f"PDF로 내보냈습니다: {file_path}", 3000)
        else:
            QMessageBox.information(self, "내보낼 내용 없음", "캔버스에 블록이 없어서 PDF를 만들지 않았습니다.")

    # --- 찾기 ---

    def _on_show_find(self) -> None:
        """
        찾기 대화상자를 연다 (메뉴 > 편집 > 찾기, Ctrl+F).

        Note:
            처음 열 때만 만들고 이후에는 재사용한다(도움말 창과 같은 패턴).
            열 때마다 검색창에 포커스를 주고 기존 텍스트를 전체 선택해서,
            바로 새 검색어를 입력할 수 있게 한다.
        """
        if self._find_dialog is None:
            self._find_dialog = FindDialog(self._scene, self._view, self)
        self._find_dialog.show()
        self._find_dialog.raise_()
        self._find_dialog.activateWindow()
        self._find_dialog.focus_input()

    # --- 도움말 ---

    def _on_show_help(self) -> None:
        """
        도움말(사용법) 대화상자를 연다.

        Note:
            처음 열 때만 만들고 이후에는 재사용한다. 모달이 아니라 show()로
            띄워서, 사용법을 보면서 동시에 캔버스에서 타이핑할 수 있게 한다.
        """
        if self._help_dialog is None:
            self._help_dialog = HelpDialog(self)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()
