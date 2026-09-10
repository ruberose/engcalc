"""
블록을 삭제하거나, 드래그 또는 속성 패널로 순서를 바꿨을 때도 문서가
다시 계산되는지 확인한다.

세 경우 모두 버그체크 중 발견된 실제 버그였다:
- 블록을 삭제해도 재계산이 안 일어나서, 삭제된 변수를 참조하던 다른 블록이
  옛날 값을 계속 보여주고 있었다 (canvas/document_view.py).
- 블록을 드래그로 옮겨서 계산 순서(화면 위→아래)가 바뀌어도 재계산이 안
  일어나서, 새 순서를 반영하지 않은 옛날 결과가 남아 있었다 (blocks/base_block.py).
- 속성 패널에서 위치를 직접 입력해서 옮긴 경우도 마찬가지였다 — 드래그
  수정은 마우스 이벤트 경로에만 걸려 있어서, 마우스를 거치지 않고
  setPos()를 직접 부르는 속성 패널은 그 수정이 적용되지 않았다
  (ui/property_panel.py).
"""

import gc

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from app.main_window import MainWindow
from blocks.math_block import MathBlock

_app = QApplication.instance() or QApplication([])


@pytest.fixture
def window():
    """
    테스트용 MainWindow 하나. 테스트가 끝나면 신호를 끊고 닫아서 정리한다.

    Note:
        MainWindow.__init__()이 self._scene.selectionChanged를 self(윈도우)의
        메서드에 연결하는데, 이게 "씬 -> 연결된 슬롯 -> bound method -> 윈도우
        -> 윈도우가 들고 있는 씬"으로 이어지는 참조 순환을 만든다. 파이썬의
        참조 카운트만으로는 이런 순환을 못 지우고 주기적인 순환 GC가 돌아야
        지워지는데, 그 타이밍이 테스트마다 정해져 있지 않다 보니, 한 프로세스
        안에서 MainWindow를 여러 개 만들고 넘어가면 앞 테스트의 씬(C++ 쪽은
        이미 정리됐지만 파이썬 객체는 순환 때문에 살아있는 상태)에 연결된 신호가
        뒤늦게 처리되다가 "Internal C++ object already deleted" 에러가 났다
        (실제 앱은 창을 하나만 쓰다 sys.exit()로 끝나서 이 문제가 없다 — 직접
        확인함). 신호 연결을 명시적으로 끊고 gc.collect()로 순환을 즉시
        정리하면 다음 테스트로 오염이 넘어가지 않는다.
    """
    win = MainWindow()
    win.show()
    for _ in range(3):
        _app.processEvents()
    yield win
    win._scene.selectionChanged.disconnect(win._on_selection_changed)
    win._scene.changed.disconnect(win._on_scene_changed)
    win._is_modified = False  # 저장 확인 대화상자 없이 바로 닫기 위함(테스트 전용 우회)
    win.close()
    _app.processEvents()
    del win
    gc.collect()
    _app.processEvents()


def _add_math_block_via_ui(win: MainWindow, x: int, y: int, text: str) -> MathBlock:
    """실제 더블클릭 -> 입력 -> 편집 종료 흐름으로 수식 블록을 만든다."""
    view = win.centralWidget()
    scene = view.scene()
    before = {id(i) for i in scene.items() if isinstance(i, MathBlock)}
    QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos=QPoint(x, y))
    _app.processEvents()
    new_blocks = [i for i in scene.items() if isinstance(i, MathBlock) and id(i) not in before]
    assert len(new_blocks) == 1
    block = new_blocks[0]
    block._editor.setPlainText(text)
    block.finish_editing()
    _app.processEvents()
    return block


def test_deleting_block_recalculates_dependents(window):
    """a를 정의한 블록을 삭제하면, a를 참조하던 블록은 즉시 에러로 바뀌어야 한다."""
    view = window.centralWidget()
    scene = view.scene()

    a = _add_math_block_via_ui(window, 150, 100, "a = 100")
    b = _add_math_block_via_ui(window, 150, 200, "b = a * 2")
    assert not b.result().is_error
    assert float(b.result().value) == 200.0

    a.setSelected(True)
    _app.processEvents()
    QTest.keyClick(view, Qt.Key.Key_Delete)
    _app.processEvents()

    assert a not in scene.items()
    assert b.result().is_error, "블록 삭제 후 재계산이 안 일어나서 옛날 값이 남아있음"
    assert "a" in b.result().error


def test_dragging_block_below_dependent_recalculates(window):
    """변수를 정의한 블록을 그걸 참조하는 블록보다 아래로 드래그하면, 재계산되어 에러가 떠야 한다."""
    view = window.centralWidget()

    a = _add_math_block_via_ui(window, 150, 100, "a = 100")
    b = _add_math_block_via_ui(window, 150, 200, "b = a * 2")
    assert not b.result().is_error

    a_center_scene = a.mapToScene(a.boundingRect().center())
    a_center_view = view.mapFromScene(a_center_scene)
    target_scene = type(a_center_scene)(a_center_scene.x(), a_center_scene.y() + 200)
    target_view = view.mapFromScene(target_scene)

    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=a_center_view)
    _app.processEvents()
    QTest.mouseMove(view.viewport(), pos=target_view)
    _app.processEvents()
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=target_view)
    _app.processEvents()

    assert a.pos().y() > b.pos().y(), "테스트 전제 실패: a가 b보다 아래로 안 옮겨짐"
    assert b.result().is_error, "드래그로 순서를 바꿨는데 재계산이 안 일어나서 옛날 값이 남아있음"


def test_property_panel_reposition_below_dependent_recalculates(window):
    """속성 패널에서 위치를 바꿔 순서가 뒤집혀도(마우스 드래그 아님) 재계산되어야 한다."""
    a = _add_math_block_via_ui(window, 150, 100, "a = 100")
    b = _add_math_block_via_ui(window, 150, 200, "b = a * 2")
    assert not b.result().is_error

    a.setSelected(True)
    _app.processEvents()

    panel = window._property_panel
    assert panel.current_block() is a
    panel._y_spin.setValue(a.pos().y() + 200)
    _app.processEvents()

    assert a.pos().y() > b.pos().y(), "테스트 전제 실패: a가 b보다 아래로 안 옮겨짐"
    assert b.result().is_error, "속성 패널로 순서를 바꿨는데 재계산이 안 일어나서 옛날 값이 남아있음"


def test_plain_click_does_not_trigger_unnecessary_recalculation(window):
    """단순 클릭(드래그 없음)은 위치가 안 바뀌므로 재계산을 유발하지 않아야 한다 (성능)."""
    from canvas.document_scene import DocumentScene

    call_count = []
    original = DocumentScene.recalculate_all

    def counted(self):
        call_count.append(1)
        return original(self)

    DocumentScene.recalculate_all = counted
    try:
        view = window.centralWidget()
        a = _add_math_block_via_ui(window, 150, 100, "a = 100")
        call_count.clear()

        pos = view.mapFromScene(a.mapToScene(a.boundingRect().center()))
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
        _app.processEvents()
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
        _app.processEvents()

        assert call_count == [], f"단순 클릭인데 recalculate_all()이 {len(call_count)}번 불림"
    finally:
        DocumentScene.recalculate_all = original
