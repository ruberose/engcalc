"""
EngCalc 앱 진입점.

QApplication을 생성하고 MainWindow를 띄운다.
이 파일에는 애플리케이션 부트스트랩 코드만 두고,
실제 UI 구성은 app/main_window.py 에 위임한다.
"""

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> None:
    """EngCalc 애플리케이션을 실행한다."""
    app = QApplication(sys.argv)
    app.setApplicationName("EngCalc")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
