import sys
import os

# Python 3.10+ 필수 — 코드 곳곳에서 PEP 604 union(예: dict | None)을 쓴다.
# 3.9 이하로 실행하면 import 도중 "unsupported operand type(s) for |" 로 죽으므로,
# 프로젝트 모듈을 import 하기 전에 여기서 먼저 막고 명확히 안내한다.
if sys.version_info < (3, 10):
    _v = ".".join(map(str, sys.version_info[:3]))
    sys.stderr.write(
        f"[InfluencerSeeder] Python 3.10 이상이 필요합니다 (현재 {_v}).\n"
        "  빌드 스크립트(build_mac.sh / build_windows.bat)를 다시 실행하면\n"
        "  3.10+ 인터프리터로 재빌드됩니다.\n"
    )
    sys.exit(1)

# QtWebEngine(Chromium)이 창 최소화/백그라운드 시 렌더러·타이머를 throttle 하지
# 않도록 — 백그라운드 수집 중에도 JS 클릭/딜레이가 정상 속도로 동작하게 한다.
# (WebEngine 초기화 전에 설정해야 적용됨)
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-renderer-backgrounding "
    "--disable-backgrounding-occluded-windows "
    "--disable-background-timer-throttling",
)

from pathlib import Path
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

try:
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
    _HAS_QTNETWORK = True
except ImportError:
    _HAS_QTNETWORK = False

from design.stylesheet import build as build_stylesheet
from ui.main_window import MainWindow

_SERVER_NAME = "InfluencerSeederSingleInstance"

# 앱 아이콘 — src/assets/icon.ico (Windows) 또는 icon.png 사용
_ASSETS = Path(__file__).resolve().parent / "assets"
_ICON_ICO = _ASSETS / "icon.ico"
_ICON_PNG = _ASSETS / "icon.png"


def _app_icon() -> QIcon:
    for p in (_ICON_ICO, _ICON_PNG):
        if p.exists():
            return QIcon(str(p))
    return QIcon()


def _try_raise_existing() -> bool:
    """기존 인스턴스에 'show' 메시지를 보내고 True 반환.
    stale pipe 오탐 방지: 서버로부터 'ok' 응답을 확인해야 True."""
    if not _HAS_QTNETWORK:
        return False
    sock = QLocalSocket()
    sock.connectToServer(_SERVER_NAME)
    if not sock.waitForConnected(300):
        return False
    sock.write(b"show")
    sock.flush()
    sock.waitForBytesWritten(300)
    # 살아있는 서버라면 'ok' 응답이 온다 — stale pipe는 응답 없음
    alive = sock.waitForReadyRead(300)
    sock.abort()
    return alive


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("인플루언서 시딩기")
    icon = _app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    # 기존 인스턴스가 있으면 복원 신호만 보내고 종료
    if _try_raise_existing():
        os._exit(0)

    app.setStyleSheet(build_stylesheet())
    window = MainWindow(icon=icon)

    # 단일 인스턴스 서버 시작
    _server = None
    if _HAS_QTNETWORK:
        _server = QLocalServer(app)
        QLocalServer.removeServer(_SERVER_NAME)  # 이전 크래시 잔여 소켓 제거
        _server.listen(_SERVER_NAME)
        _server.newConnection.connect(lambda: _handle_new_connection(_server, window))

    window.show()
    app.exec()

    # 서버 명시 정리 → Windows named pipe stale 방지
    if _server is not None:
        _server.close()
        QLocalServer.removeServer(_SERVER_NAME)

    # os._exit: QThread/QLocalServer 잔류 객체까지 강제 종료 (좀비 프로세스 방지)
    os._exit(0)


def _handle_new_connection(server: "QLocalServer", window: MainWindow):
    """두 번째 실행 시도 → 기존 창 복원."""
    conn = server.nextPendingConnection()
    if conn:
        conn.waitForReadyRead(300)
        conn.write(b"ok")   # liveness 응답 (클라이언트 stale-pipe 오탐 방지)
        conn.flush()
        conn.close()
    window._restore_from_tray()


if __name__ == "__main__":
    main()
