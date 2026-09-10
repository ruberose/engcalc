"""
블록을 삭제하거나 드래그로 순서를 바꿨을 때도 문서가 다시 계산되는지 확인.

두 경우 모두 버그체크 중 발견된 실제 버그였다:
- 블록을 삭제해도 재계산이 안 일어나서, 삭제된 변수를 참조하던 다른 블록이
  옛날 값을 계속 보여주고 있었다 (canvas/document_view.py).
- 블록을 드래그로 옮겨서 계산 순서(화면 위→아래)가 바뀌어도 재계산이 안
  일어나서, 새 순서를 반영하지 않은 옛날 결과가 남아 있었다 (blocks/base_block.py).
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from app.main_window import MainWindow
from blocks.math_block import MathBlock

_app = QApplication.instance() or QApplication([])


def _add_math_block_via_ui(window: MainWindow, x: int, y: int, text: str) -> MathBlock:
    """실제 더블클릭 -> 입력 -> 편집 종료 흐름으로 수식 블록을 만든다."""
    view = window.centralWidget()
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


def test_deleting_block_recalculates_dependents():
    """a를 정의한 블록을 삭제하면, a를 참조하던 블록은 즉시 에러로 바뀌어야 한다."""
    window = MainWindow()
    window.show()
    for _ in range(3):
        _app.processEvents()
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


def test_dragging_block_below_dependent_recalculates():
    """변수를 정의한 블록을 그걸 참조하는 블록보다 아래로 드래그하면, 재계산되어 에러가 떠야 한다."""
    window = MainWindow()
    window.show()
    for _ in range(3):
        _app.processEvents()
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


def test_plain_click_does_not_trigger_unnecessary_recalculation():
    """단순 클릭(드래그 없음)은 위치가 안 바뀌므로 재계산을 유발하지 않아야 한다 (성능)."""
    from canvas.document_scene import DocumentScene

    call_count = []
    original = DocumentScene.recalculate_all

    def counted(self):
        call_count.append(1)
        return original(self)

    DocumentScene.recalculate_all = counted
    try:
        window = MainWindow()
        window.show()
        for _ in range(3):
            _app.processEvents()
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
