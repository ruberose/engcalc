"""ui/variable_inspector.py + DocumentScene의 변수 추적 기능 단위 테스트."""

from PySide6.QtWidgets import QApplication

from blocks.math_block import MathBlock
from canvas.document_scene import DocumentScene
from ui.variable_inspector import VariableInspector

_app = QApplication.instance() or QApplication([])


def _make_math_block(scene: DocumentScene, x: float, y: float, text: str) -> MathBlock:
    block = MathBlock(position=(x, y))
    block.set_input_text(text)
    scene.addItem(block)
    return block


def test_scene_tracks_variables_after_recalculate():
    """recalculate_all() 후 scene.variables()에 정의된 변수가 전부 나와야 한다."""
    scene = DocumentScene()
    _make_math_block(scene, 0, 0, "a = 100")
    _make_math_block(scene, 0, 60, "b = a * 2")
    _make_math_block(scene, 0, 120, "a * b")  # 대입이 아니므로 변수로 등록되지 않음

    scene.recalculate_all()

    names = set(scene.variables().keys())
    assert names == {"a", "b"}
    assert float(scene.variables()["b"]) == 200.0


def test_scene_maps_variable_name_to_defining_block():
    """block_for_variable()은 그 변수를 실제로 정의한 블록을 돌려줘야 한다."""
    scene = DocumentScene()
    block_a = _make_math_block(scene, 0, 0, "a = 100")
    scene.recalculate_all()

    assert scene.block_for_variable("a") is block_a
    assert scene.block_for_variable("정의안됨") is None


def test_scene_emits_variables_changed_on_recalculate():
    """recalculate_all()을 호출하면 variables_changed 신호가 울려야 한다."""
    scene = DocumentScene()
    _make_math_block(scene, 0, 0, "a = 1")

    fired = []
    scene.variables_changed.connect(lambda: fired.append(True))
    scene.recalculate_all()

    assert fired == [True]


def test_variable_inspector_lists_variables_and_updates_on_change():
    """VariableInspector는 scene의 변수 목록을 리스트로 보여주고, 재계산되면 갱신되어야 한다."""
    scene = DocumentScene()
    block_a = _make_math_block(scene, 0, 0, "a = 100")
    scene.recalculate_all()

    inspector = VariableInspector()
    inspector.set_scene(scene)
    assert inspector._list.count() == 1
    assert "a = 100" in inspector._list.item(0).text()

    _make_math_block(scene, 0, 60, "b = 5")
    scene.recalculate_all()  # variables_changed가 울려서 inspector가 자동으로 다시 그려야 함

    assert inspector._list.count() == 2
    texts = {inspector._list.item(i).text() for i in range(inspector._list.count())}
    assert "a = 100" in texts
    assert "b = 5" in texts


def test_double_click_variable_emits_block_activated():
    """변수 항목을 더블클릭하면 그 변수를 정의한 블록을 실어 block_activated가 울려야 한다."""
    scene = DocumentScene()
    block_a = _make_math_block(scene, 0, 0, "a = 100")
    scene.recalculate_all()

    inspector = VariableInspector()
    inspector.set_scene(scene)

    activated = []
    inspector.block_activated.connect(lambda block: activated.append(block))
    inspector._on_item_double_clicked(inspector._list.item(0))

    assert activated == [block_a]
