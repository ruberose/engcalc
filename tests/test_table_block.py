"""blocks/table_block.py 단위 테스트."""

from PySide6.QtWidgets import QApplication

from blocks.table_block import DEFAULT_COLS, DEFAULT_ROWS, TableBlock

_app = QApplication.instance() or QApplication([])


def test_default_size_is_three_by_three():
    """기본으로 만들면 3행 3열, 모든 칸이 빈 문자열이어야 한다."""
    block = TableBlock(position=(0, 0))
    assert block.row_count() == DEFAULT_ROWS
    assert block.col_count() == DEFAULT_COLS
    assert block.cell_text(0, 0) == ""


def test_custom_row_col_count_on_creation():
    """rows/cols를 지정하면 그 크기로 만들어져야 한다."""
    block = TableBlock(position=(0, 0), rows=2, cols=4)
    assert block.row_count() == 2
    assert block.col_count() == 4


def test_set_and_get_cell_text():
    """칸 내용을 설정하면 그대로 읽힌다."""
    block = TableBlock(position=(0, 0))
    block.set_cell_text(1, 2, "300 mm")
    assert block.cell_text(1, 2) == "300 mm"


def test_bounding_rect_grows_with_content():
    """글자가 긴 칸이 있으면 표 전체 너비가 그만큼 넓어져야 한다."""
    block = TableBlock(position=(0, 0), rows=1, cols=1)
    narrow_width = block.boundingRect().width()

    block.set_cell_text(0, 0, "아주 긴 텍스트를 넣으면 칸이 넓어져야 함")
    wide_width = block.boundingRect().width()

    assert wide_width > narrow_width


def test_add_row_inserts_after_given_index():
    """add_row(after=0)은 0번 행 바로 다음(1번)에 빈 행을 추가해야 한다."""
    block = TableBlock(position=(0, 0), rows=2, cols=2)
    block.set_cell_text(0, 0, "위")
    block.set_cell_text(1, 0, "아래")

    block.add_row(after=0)

    assert block.row_count() == 3
    assert block.cell_text(0, 0) == "위"
    assert block.cell_text(1, 0) == ""  # 새로 끼워 넣은 빈 행
    assert block.cell_text(2, 0) == "아래"


def test_remove_row_deletes_given_index():
    """remove_row(index)는 그 행을 지우고 나머지를 그대로 유지해야 한다."""
    block = TableBlock(position=(0, 0), rows=3, cols=1)
    block.set_cell_text(0, 0, "a")
    block.set_cell_text(1, 0, "b")
    block.set_cell_text(2, 0, "c")

    block.remove_row(1)

    assert block.row_count() == 2
    assert block.cell_text(0, 0) == "a"
    assert block.cell_text(1, 0) == "c"


def test_cannot_remove_last_remaining_row():
    """행이 1개뿐이면 remove_row가 조용히 무시되어야 한다(표가 아예 사라지면 안 됨)."""
    block = TableBlock(position=(0, 0), rows=1, cols=1)
    block.remove_row(0)
    assert block.row_count() == 1


def test_add_and_remove_col():
    """add_col/remove_col도 행과 동일하게 동작해야 한다."""
    block = TableBlock(position=(0, 0), rows=1, cols=2)
    block.set_cell_text(0, 0, "a")
    block.set_cell_text(0, 1, "b")

    block.add_col(after=0)
    assert block.col_count() == 3
    assert block.cell_text(0, 0) == "a"
    assert block.cell_text(0, 1) == ""
    assert block.cell_text(0, 2) == "b"

    block.remove_col(1)
    assert block.col_count() == 2
    assert block.cell_text(0, 0) == "a"
    assert block.cell_text(0, 1) == "b"


def test_cannot_remove_last_remaining_col():
    """열이 1개뿐이면 remove_col이 조용히 무시되어야 한다."""
    block = TableBlock(position=(0, 0), rows=1, cols=1)
    block.remove_col(0)
    assert block.col_count() == 1


def test_set_row_count_grows_and_shrinks_at_the_end():
    """속성 패널의 행 수 입력처럼, 끝에 추가/삭제하면서 개수를 맞춰야 한다."""
    block = TableBlock(position=(0, 0), rows=2, cols=1)
    block.set_cell_text(0, 0, "a")
    block.set_cell_text(1, 0, "b")

    block.set_row_count(4)
    assert block.row_count() == 4
    assert block.cell_text(0, 0) == "a"
    assert block.cell_text(1, 0) == "b"

    block.set_row_count(1)
    assert block.row_count() == 1
    assert block.cell_text(0, 0) == "a"


def test_set_col_count_grows_and_shrinks_at_the_end():
    """열 수도 행 수와 동일한 방식으로 조절되어야 한다."""
    block = TableBlock(position=(0, 0), rows=1, cols=2)
    block.set_cell_text(0, 0, "a")
    block.set_cell_text(0, 1, "b")

    block.set_col_count(3)
    assert block.col_count() == 3
    assert block.cell_text(0, 0) == "a"
    assert block.cell_text(0, 1) == "b"

    block.set_col_count(1)
    assert block.col_count() == 1
    assert block.cell_text(0, 0) == "a"


def test_serialize_deserialize_round_trip():
    """직렬화 후 새 블록에 복원하면 위치/칸 내용/글자 크기가 그대로 돌아와야 한다."""
    original = TableBlock(position=(50, 80), rows=2, cols=2)
    original.set_cell_text(0, 0, "부재")
    original.set_cell_text(0, 1, "단면적")
    original.set_cell_text(1, 0, "C1")
    original.set_cell_text(1, 1, "150000 mm^2")
    original.set_font_size(16)

    data = original.serialize()
    assert data["type"] == "table"
    assert data["position"] == [50.0, 80.0]
    assert data["cells"] == [["부재", "단면적"], ["C1", "150000 mm^2"]]
    assert data["font_size"] == 16

    restored = TableBlock()
    restored.deserialize(data)

    assert restored.pos().toTuple() == (50.0, 80.0)
    assert restored.row_count() == 2
    assert restored.col_count() == 2
    assert restored.cell_text(1, 1) == "150000 mm^2"
    assert restored.font_size() == 16


def test_cell_editing_updates_cell_text():
    """start_cell_editing()으로 편집을 시작하고 finish_cell_editing()으로 끝내면 그 칸 내용이 바뀌어야 한다."""
    block = TableBlock(position=(0, 0), rows=1, cols=1)
    block.start_cell_editing((0, 0))
    block._editor.setPlainText("300 mm")
    block.finish_cell_editing()

    assert block.cell_text(0, 0) == "300 mm"
    assert block._editor is None  # 편집이 끝나면 편집기가 사라져야 함


def test_tab_moves_editing_to_next_cell():
    """편집 중 move_to_next=True로 끝내면(Tab) 바로 다음 칸 편집으로 이어져야 한다."""
    block = TableBlock(position=(0, 0), rows=1, cols=2)
    block.start_cell_editing((0, 0))
    block._editor.setPlainText("첫 칸")
    block.finish_cell_editing(move_to_next=True)

    assert block.cell_text(0, 0) == "첫 칸"
    assert block._editing_cell == (0, 1)  # 다음 칸 편집이 곧바로 시작됨


def test_locked_block_cannot_start_editing():
    """잠긴 표는 편집을 시작할 수 없어야 한다 (다른 블록들과 동일한 규칙)."""
    block = TableBlock(position=(0, 0))
    block.set_locked(True)
    block.start_cell_editing((0, 0))
    assert block._editor is None
