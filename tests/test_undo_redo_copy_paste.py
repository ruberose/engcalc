"""
실행취소/다시실행(Ctrl+Z/Ctrl+Y)과 복사/붙여넣기(Ctrl+C/Ctrl+V) 검증.

사용자 요청: "실행취소, 복사 붙여넣기는 꼭 필요한거네."

구현 방식: 문서 전체를 to_blocks_list()로 스냅샷 떠서 스택에 쌓는다
(파일 저장/불러오기에 이미 쓰는 직렬화 골격을 재사용). 그래서 여기서는
DocumentScene의 capture_undo_snapshot()/commit_undo_snapshot()/undo()/redo()/
copy_selected_blocks()/paste_blocks() 를 직접 호출해서 검증한다.
"""

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from blocks.image_block import ImageBlock
from blocks.math_block import MathBlock
from blocks.text_block import TextBlock
from canvas.document_scene import DocumentScene

_app = QApplication.instance() or QApplication([])


def _math_blocks(scene: DocumentScene) -> list[MathBlock]:
    return [item for item in scene.items() if isinstance(item, MathBlock)]


def _text_blocks(scene: DocumentScene) -> list[TextBlock]:
    return [item for item in scene.items() if isinstance(item, TextBlock)]


# --- 실행취소 / 다시실행 기본 동작 ---


def test_undo_redo_empty_stacks_do_nothing():
    """되돌릴 게 없으면 undo()/redo()를 불러도 조용히 아무 일도 없어야 한다."""
    scene = DocumentScene()
    assert not scene.can_undo()
    assert not scene.can_redo()
    scene.undo()
    scene.redo()
    assert scene.to_blocks_list() == []


def test_commit_undo_snapshot_ignores_noop_change():
    """before와 지금 상태가 똑같으면(아무것도 안 바뀌었으면) 기록하지 않는다."""
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    scene.addItem(block)

    before = scene.capture_undo_snapshot()
    scene.commit_undo_snapshot(before)  # 아무것도 안 바뀐 채로 커밋 시도

    assert not scene.can_undo()


def test_block_creation_is_undoable():
    """블록 생성(더블클릭)은 한 번의 Ctrl+Z로 통째로 사라져야 한다."""
    scene = DocumentScene()
    block = scene._create_math_block(QPointF(100, 100))
    block.finish_editing()  # 편집기 그대로 두면 아직 확정 전 상태이므로 명시적으로 종료

    assert len(_math_blocks(scene)) == 1
    assert scene.can_undo()

    scene.undo()
    assert len(_math_blocks(scene)) == 0
    assert scene.can_redo()

    scene.redo()
    assert len(_math_blocks(scene)) == 1


def test_creating_empty_block_without_typing_is_still_undoable():
    """새로 만든 블록에 아무것도 안 쓰고 바로 편집을 끝내도(빈 블록), 그 생성 자체는 실행취소할 수 있어야 한다."""
    scene = DocumentScene()
    scene._create_math_block(QPointF(50, 50))
    assert len(_math_blocks(scene)) == 1

    # 편집기를 그대로 finish_editing()만 호출 (아무것도 타이핑하지 않음)
    _math_blocks(scene)[0].finish_editing()

    assert scene.can_undo()
    scene.undo()
    assert len(_math_blocks(scene)) == 0


def test_editing_existing_block_without_change_does_not_add_undo_step():
    """기존 블록을 열어봤다가 아무것도 안 바꾸고 닫으면, 실행취소 기록이 늘지 않아야 한다."""
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    scene.addItem(block)
    scene.recalculate_all()

    assert not scene.can_undo()  # 준비 단계까지는 아직 아무 기록도 없음

    block.start_editing()
    block._editor.setPlainText("a = 1")  # 똑같은 내용 그대로
    block.finish_editing()

    assert not scene.can_undo()


def test_editing_block_text_is_undoable():
    """수식 블록의 내용을 실제로 바꾸면 실행취소로 원래 텍스트로 돌아가야 한다."""
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    block.set_input_text("a = 1")
    scene.addItem(block)
    scene.recalculate_all()

    block.start_editing()
    block._editor.setPlainText("a = 2")
    block.finish_editing()

    assert block.input_text() == "a = 2"
    assert scene.can_undo()

    scene.undo()
    restored = _math_blocks(scene)[0]
    assert restored.input_text() == "a = 1"


def test_deleting_block_is_undoable():
    """블록 삭제 후 실행취소하면 블록이 되살아나야 한다."""
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    block.set_input_text("x = 5")
    scene.addItem(block)
    scene.recalculate_all()

    before = scene.capture_undo_snapshot()
    scene.removeItem(block)
    scene.commit_undo_snapshot(before)
    scene.recalculate_all()

    assert len(_math_blocks(scene)) == 0

    scene.undo()
    restored = _math_blocks(scene)
    assert len(restored) == 1
    assert restored[0].input_text() == "x = 5"


def test_new_action_after_undo_clears_redo_stack():
    """실행취소한 뒤 새로운 변경을 하면, 그 시점부터의 다시실행 기록은 사라져야 한다."""
    scene = DocumentScene()
    block1 = scene._create_math_block(QPointF(0, 0))
    block1.finish_editing()
    block2 = scene._create_math_block(QPointF(0, 60))
    block2.finish_editing()

    scene.undo()  # block2 생성 취소
    assert scene.can_redo()

    block3 = scene._create_math_block(QPointF(0, 120))
    block3.finish_editing()

    assert not scene.can_redo()  # 새 변경이 생겼으니 이전 redo 기록은 무효화됨


def test_move_drag_undo_restores_original_position():
    """블록을 드래그로 옮긴 뒤 실행취소하면 원래 위치로 돌아가야 한다 (press/release 시뮬레이션)."""
    scene = DocumentScene()
    block = MathBlock(position=(10, 20))
    block.set_input_text("a = 1")
    scene.addItem(block)
    scene.recalculate_all()

    before = scene.capture_undo_snapshot()
    block.setPos(200, 300)
    scene.commit_undo_snapshot(before)

    assert block.pos().x() == 200
    assert scene.can_undo()

    scene.undo()
    restored = _math_blocks(scene)[0]
    assert (restored.pos().x(), restored.pos().y()) == (10, 20)


def test_undo_stack_capped_at_max_steps():
    """실행취소 스택은 MAX_UNDO_STEPS를 넘으면 오래된 것부터 버려야 한다."""
    from canvas.document_scene import MAX_UNDO_STEPS

    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    scene.addItem(block)

    for i in range(MAX_UNDO_STEPS + 10):
        before = scene.capture_undo_snapshot()
        block.setPos(i, i)
        scene.commit_undo_snapshot(before)

    assert len(scene._undo_stack) == MAX_UNDO_STEPS


# --- 전체 선택 ---


def test_select_all_blocks_selects_every_block():
    scene = DocumentScene()
    math_block = MathBlock(position=(0, 0))
    text_block = TextBlock(position=(0, 100))
    image_block = ImageBlock(position=(0, 200))
    for block in (math_block, text_block, image_block):
        scene.addItem(block)

    scene.select_all_blocks()

    assert all(block.isSelected() for block in (math_block, text_block, image_block))


def test_select_all_blocks_on_empty_scene_does_nothing():
    """빈 씬에서 불러도 예외 없이 조용히 아무 일도 없어야 한다."""
    scene = DocumentScene()
    scene.select_all_blocks()  # 예외만 안 나면 충분
    assert scene.selectedItems() == []


def test_select_all_blocks_extends_partial_selection():
    """일부만 선택된 상태에서 불러도 나머지까지 전부 선택돼야 한다."""
    scene = DocumentScene()
    a = MathBlock(position=(0, 0))
    b = MathBlock(position=(0, 100))
    scene.addItem(a)
    scene.addItem(b)
    a.setSelected(True)

    scene.select_all_blocks()

    assert a.isSelected()
    assert b.isSelected()


# --- 복사 / 붙여넣기 ---


def test_paste_without_copy_does_nothing():
    """아무것도 복사한 적 없으면 붙여넣기는 빈 리스트를 돌려주고 아무 일도 없어야 한다."""
    scene = DocumentScene()
    assert not scene.can_paste()
    assert scene.paste_blocks() == []


def test_copy_paste_creates_duplicate_with_offset_and_new_id():
    """복사 후 붙여넣으면 내용은 같고 위치는 어긋난, id가 다른 새 블록이 생긴다."""
    scene = DocumentScene()
    original = MathBlock(position=(100, 100))
    original.set_input_text("F = 200 kN")
    scene.addItem(original)
    scene.recalculate_all()
    original.setSelected(True)

    scene.copy_selected_blocks()
    assert scene.can_paste()

    pasted = scene.paste_blocks()
    assert len(pasted) == 1
    new_block = pasted[0]

    assert new_block.block_id != original.block_id
    assert new_block.input_text() == "F = 200 kN"
    assert new_block.pos() != original.pos()
    assert new_block.isSelected()
    assert not original.isSelected()  # 붙여넣은 블록만 선택 상태로 남는다


def test_paste_is_undoable():
    """붙여넣기도 한 번의 실행취소로 통째로 사라져야 한다."""
    scene = DocumentScene()
    original = TextBlock(position=(0, 0))
    original.set_text("제목")
    scene.addItem(original)
    original.setSelected(True)
    scene.copy_selected_blocks()

    scene.paste_blocks()
    assert len(_text_blocks(scene)) == 2

    scene.undo()
    assert len(_text_blocks(scene)) == 1


def test_copy_paste_works_across_block_types():
    """수식/텍스트/이미지 블록을 함께 선택해서 복사/붙여넣기해도 각자 종류에 맞게 복제된다."""
    scene = DocumentScene()
    math_block = MathBlock(position=(0, 0))
    math_block.set_input_text("a = 1")
    text_block = TextBlock(position=(0, 100))
    text_block.set_text("설명")
    image_block = ImageBlock(position=(0, 200))
    scene.addItem(math_block)
    scene.addItem(text_block)
    scene.addItem(image_block)
    scene.recalculate_all()

    for item in (math_block, text_block, image_block):
        item.setSelected(True)

    scene.copy_selected_blocks()
    pasted = scene.paste_blocks()

    assert len(pasted) == 3
    assert {type(b) for b in pasted} == {MathBlock, TextBlock, ImageBlock}


def test_copy_selected_blocks_with_nothing_selected_clears_clipboard():
    """아무것도 선택하지 않은 채 복사하면 클립보드가 비워진다(이전 복사 내용도 사라짐)."""
    scene = DocumentScene()
    block = TextBlock(position=(0, 0))
    scene.addItem(block)
    block.setSelected(True)
    scene.copy_selected_blocks()
    assert scene.can_paste()

    scene.clearSelection()
    scene.copy_selected_blocks()
    assert not scene.can_paste()


# --- 복제 (Ctrl+D) ---


def test_duplicate_with_nothing_selected_does_nothing():
    """선택된 블록이 없으면 빈 리스트를 돌려주고 아무 일도 없어야 한다."""
    scene = DocumentScene()
    block = MathBlock(position=(0, 0))
    scene.addItem(block)

    assert scene.duplicate_selected_blocks() == []
    assert len(_math_blocks(scene)) == 1


def test_duplicate_creates_copy_with_offset_and_new_id():
    """복제하면 내용은 같고 위치는 어긋난, id가 다른 새 블록이 바로 생겨야 한다."""
    scene = DocumentScene()
    original = MathBlock(position=(100, 100))
    original.set_input_text("F = 200 kN")
    scene.addItem(original)
    scene.recalculate_all()
    original.setSelected(True)

    duplicated = scene.duplicate_selected_blocks()

    assert len(duplicated) == 1
    new_block = duplicated[0]
    assert new_block.block_id != original.block_id
    assert new_block.input_text() == "F = 200 kN"
    assert new_block.pos() != original.pos()
    assert new_block.isSelected()
    assert not original.isSelected()  # 복제된 블록만 선택 상태로 남는다
    assert len(_math_blocks(scene)) == 2


def test_duplicate_does_not_touch_clipboard():
    """복제는 클립보드를 거치지 않으므로, 이전에 복사해둔 내용이 그대로 남아있어야 한다."""
    scene = DocumentScene()
    copied_source = TextBlock(position=(0, 0))
    copied_source.set_text("복사해둔 내용")
    to_duplicate = TextBlock(position=(0, 100))
    to_duplicate.set_text("복제할 내용")
    scene.addItem(copied_source)
    scene.addItem(to_duplicate)

    copied_source.setSelected(True)
    scene.copy_selected_blocks()
    assert scene.can_paste()

    copied_source.setSelected(False)
    to_duplicate.setSelected(True)
    scene.duplicate_selected_blocks()

    assert scene.can_paste()
    pasted = scene.paste_blocks()
    assert len(pasted) == 1
    assert pasted[0].text() == "복사해둔 내용"  # 복제가 클립보드를 덮어쓰지 않았음을 확인


def test_duplicate_is_undoable():
    """복제도 한 번의 실행취소로 통째로 사라져야 한다."""
    scene = DocumentScene()
    block = TextBlock(position=(0, 0))
    block.set_text("제목")
    scene.addItem(block)
    block.setSelected(True)

    scene.duplicate_selected_blocks()
    assert len(_text_blocks(scene)) == 2

    scene.undo()
    assert len(_text_blocks(scene)) == 1


def test_duplicate_works_across_block_types():
    """수식/텍스트/이미지 블록을 함께 선택해서 복제해도 각자 종류에 맞게 복제된다."""
    scene = DocumentScene()
    math_block = MathBlock(position=(0, 0))
    math_block.set_input_text("a = 1")
    text_block = TextBlock(position=(0, 100))
    text_block.set_text("설명")
    image_block = ImageBlock(position=(0, 200))
    scene.addItem(math_block)
    scene.addItem(text_block)
    scene.addItem(image_block)
    scene.recalculate_all()

    for item in (math_block, text_block, image_block):
        item.setSelected(True)

    duplicated = scene.duplicate_selected_blocks()

    assert len(duplicated) == 3
    assert {type(b) for b in duplicated} == {MathBlock, TextBlock, ImageBlock}
