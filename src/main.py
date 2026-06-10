import sys
from PyQt6.QtWidgets import QApplication

try:
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
    _HAS_QTNETWORK = True
except ImportError:
    _HAS_QTNETWORK = False

from design.stylesheet import build as build_stylesheet
from ui.main_window import MainWindow

_SERVER_NAME = "InfluencerSeederSingleInstance"


def _try_raise_existing() -> bool:
    """기존 인스턴스에 'show' 메시지를 보내고 True 반환. 없으면 False."""
    if not _HAS_QTNETWORK:
        return False
    sock = QLocalSocket()
    sock.connectToServer(_SERVER_NAME)
    if sock.waitForConnected(500):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(500)
        sock.disconnectFromServer()
        return True
    return False


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("인플루언서 시딩기")

    # 기존 인스턴스가 있으면 복원 신호만 보내고 종료
    if _try_raise_existing():
        sys.exit(0)

    app.setStyleSheet(build_stylesheet())
    window = MainWindow()

    # 단일 인스턴스 서버 시작
    if _HAS_QTNETWORK:
        server = QLocalServer(app)
        QLocalServer.removeServer(_SERVER_NAME)  # 이전 크래시 잔여 소켓 제거
        server.listen(_SERVER_NAME)
        server.newConnection.connect(lambda: _handle_new_connection(server, window))

    window.show()
    sys.exit(app.exec())


def _handle_new_connection(server: "QLocalServer", window: MainWindow):
    """두 번째 실행 시도 → 기존 창 복원."""
    conn = server.nextPendingConnection()
    if conn:
        conn.waitForReadyRead(300)
        conn.close()
    window._restore_from_tray()


if __name__ == "__main__":
    main()
