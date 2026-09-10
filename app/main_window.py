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

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMenu, QMessageBox

from app.settings import add_recent_file, get_recent_files
from blocks.image_block import SUPPORTED_EXTENSIONS
from canvas.document_scene import DocumentScene
from canvas.document_view import DocumentView
from file_io.file_manager import load_document, save_document

#: QFileDialog에 보여줄 확장자 필터 문자열 (예: "*.png *.jpg *.jpeg *.bmp *.svg").
_IMAGE_FILE_FILTER = "이미지 파일 (" + " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS) + ")"

#: .engcalc 파일 관련 상수.
_FILE_EXTENSION = ".engcalc"
_FILE_FILTER = "EngCalc 문서 (*.engcalc)"
_DOCUMENT_VERSION = "1.0"
_DEFAULT_TITLE = "제목 없음"


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

        self.resize(1200, 800)

        # --- 현재 문서 상태 ---
        self._current_file_path: str | None = None
        self._created_at: str = datetime.now().isoformat()
        self._is_modified: bool = False

        # 메뉴의 "이미지 삽입"/"열기" 등이 self._scene/self._view를 참조하므로
        # 캔버스를 먼저 만들어야 한다.
        self._create_canvas()
        self._create_menu_bar()
        self.statusBar().showMessage(
            "준비됨 — 더블클릭: 수식 블록 추가 / Ctrl+더블클릭: 텍스트 블록 추가"
        )
        self._update_window_title()

        # QGraphicsScene.changed는 최초 화면이 그려질 때도 한 번 울린다(빈 캔버스를
        # 처음 페인트하는 것도 "변경"으로 잡히기 때문). 그걸 실제 사용자 수정으로
        # 오인하지 않도록, 이번 이벤트 루프 한 바퀴가 끝난 뒤에 플래그를 정리한다.
        QTimer.singleShot(0, self._reset_modified_flag)

    def _reset_modified_flag(self) -> None:
        """초기 렌더링으로 인해 잘못 켜진 "수정됨" 표시를 끈다."""
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

        for title in ("편집(&E)", "보기(&V)", "도움말(&H)"):
            menu = menu_bar.addMenu(title)
            self._add_placeholder(menu)

    def _add_placeholder(self, menu: QMenu) -> None:
        """메뉴에 "(구현 예정)" 비활성 항목을 하나 추가한다."""
        placeholder = menu.addAction("(구현 예정)")
        placeholder.setEnabled(False)

    # --- 수정 감지 / 창 제목 ---

    def _on_scene_changed(self, _regions: list) -> None:
        """캔버스에 뭔가 변화가 생기면 "수정됨" 표시를 하고 창 제목을 갱신한다."""
        if not self._is_modified:
            self._is_modified = True
            self._update_window_title()

    def _update_window_title(self) -> None:
        """창 제목을 "[*]파일명 - EngCalc" 형태로 갱신한다."""
        name = Path(self._current_file_path).stem if self._current_file_path else _DEFAULT_TITLE
        mark = "*" if self._is_modified else ""
        self.setWindowTitle(f"{mark}{name} - EngCalc")

    # --- 새로 만들기 / 열기 / 저장 ---

    def _on_new_document(self) -> None:
        """현재 문서를 비우고 새 문서를 시작한다 (저장 안 한 변경사항이 있으면 먼저 물어봄)."""
        if not self._confirm_discard_changes():
            return
        self._scene.load_blocks_list([])
        self._current_file_path = None
        self._created_at = datetime.now().isoformat()
        self._is_modified = False
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

        self._scene.load_blocks_list(data.get("blocks", []))
        metadata = data.get("metadata", {})
        self._created_at = metadata.get("created", datetime.now().isoformat())
        self._current_file_path = file_path
        self._is_modified = False

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
