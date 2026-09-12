"""
canvas/document_view.py — 마우스 휠(기본 스크롤 / Ctrl+휠 확대·축소), 휠 버튼
(가운데 버튼) 드래그 패닝 검증.

사용자 요청: "마우스 휠은 위 아래 스크롤, 컨트롤 + 휠은 확대/축소, 휠버튼
누르면 화면 끌어당기기(이동)으로 바꿔보자" — 예전엔 휠만으로 항상 확대/축소
했었는데, 그 자리를 Ctrl+휠로 옮기고 휠 하나만 굴리면 기본 스크롤이 되게,
그리고 휠 버튼 드래그로 패닝하는 기능을 새로 추가했다.
"""

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from canvas.document_scene import DocumentScene
from canvas.document_view import MAX_SCALE, DocumentView

_app = QApplication.instance() or QApplication([])


def _make_view() -> DocumentView:
    """
    스크롤바가 실제로 움직일 수 있도록, 작은 뷰포트 + 기본 크기(4000x4000) 씬으로 만든다.

    Note:
        QGraphicsView는 씬을 "소유"하지 않고 포인터로만 연결한다(연결 위치는
        app/main_window.py의 _create_canvas() 주석 참고) — 그래서 scene을
        이 함수의 지역 변수로만 두면, 함수가 끝나는 순간 파이썬 참조가 사라져
        가비지 컬렉터가 씬을 지워버리고, view는 끊어진 포인터만 남는다. 실제로
        이 상태에서 스크롤바 maximum()이 조용히 0으로 나오는 걸 겪었다 —
        view에 씬을 직접 붙잡아둬서(keep-alive) 함수를 벗어나도 살아있게 한다.
    """
    scene = DocumentScene()
    view = DocumentView(scene)
    view._scene_keep_alive = scene
    view.resize(300, 300)
    view.show()
    QTest.qWaitForWindowExposed(view)
    for _ in range(5):
        _app.processEvents()
    return view


def _wheel_event(angle_delta_y: int, ctrl: bool = False) -> QWheelEvent:
    modifiers = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    return QWheelEvent(
        QPointF(50, 50),
        QPointF(50, 50),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def _mouse_event(event_type: QEvent.Type, pos: QPointF, button=Qt.MouseButton.MiddleButton) -> QMouseEvent:
    return QMouseEvent(event_type, pos, pos, button, button, Qt.KeyboardModifier.NoModifier)


# --- 휠: 기본 스크롤 / Ctrl+휠 확대·축소 ---


def test_plain_wheel_does_not_zoom():
    view = _make_view()
    original_scale = view._current_scale

    view.wheelEvent(_wheel_event(120, ctrl=False))

    assert view._current_scale == original_scale


def test_ctrl_wheel_up_zooms_in():
    view = _make_view()
    original_scale = view._current_scale

    view.wheelEvent(_wheel_event(120, ctrl=True))

    assert view._current_scale > original_scale


def test_ctrl_wheel_down_zooms_out():
    view = _make_view()
    original_scale = view._current_scale

    view.wheelEvent(_wheel_event(-120, ctrl=True))

    assert view._current_scale < original_scale


def test_plain_wheel_scrolls_vertical_scrollbar():
    view = _make_view()
    v_bar = view.verticalScrollBar()
    assert v_bar.maximum() > 0  # 4000x4000 씬이 300x300 뷰보다 훨씬 크므로 스크롤 범위가 있어야 함
    v_bar.setValue(v_bar.maximum() // 2)  # 양쪽 다 움직일 여유를 두려고 중간으로 옮겨둠
    original_value = v_bar.value()

    view.wheelEvent(_wheel_event(-120, ctrl=False))
    _app.processEvents()

    assert v_bar.value() != original_value


def test_zoom_respects_max_scale_limit():
    view = _make_view()
    for _ in range(200):  # 한계까지 계속 확대해봄
        view.wheelEvent(_wheel_event(120, ctrl=True))

    assert view._current_scale <= MAX_SCALE


# --- 휠 버튼(가운데 버튼) 드래그로 패닝 ---


def test_middle_button_press_starts_panning():
    view = _make_view()
    view.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, QPointF(50, 50)))
    assert view._panning is True


def test_left_button_press_does_not_start_panning():
    view = _make_view()
    view.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, QPointF(50, 50), button=Qt.MouseButton.LeftButton)
    )
    assert view._panning is False


def test_middle_button_drag_moves_scrollbars():
    view = _make_view()
    h_bar = view.horizontalScrollBar()
    v_bar = view.verticalScrollBar()
    assert h_bar.maximum() > 0
    assert v_bar.maximum() > 0
    h_bar.setValue(h_bar.maximum() // 2)
    v_bar.setValue(v_bar.maximum() // 2)
    original_h = h_bar.value()
    original_v = v_bar.value()

    view.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, QPointF(150, 150)))
    view.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, QPointF(100, 100)))  # 왼쪽 위로 50px 드래그

    assert h_bar.value() != original_h
    assert v_bar.value() != original_v


def test_middle_button_release_stops_panning():
    view = _make_view()
    view.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, QPointF(50, 50)))
    assert view._panning is True

    view.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, QPointF(50, 50)))

    assert view._panning is False


def test_panning_does_not_continue_after_release():
    view = _make_view()
    h_bar = view.horizontalScrollBar()
    h_bar.setValue(h_bar.maximum() // 2)

    view.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, QPointF(150, 150)))
    view.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, QPointF(150, 150)))
    value_after_release = h_bar.value()

    # 놓은 뒤에 움직이는 이벤트가 더 와도(예: 관성 등) 더는 패닝으로 처리되면 안 된다
    view.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, QPointF(50, 50)))

    assert h_bar.value() == value_after_release
