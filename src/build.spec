# -*- mode: python ; coding: utf-8 -*-
import sys
import platform
from pathlib import Path

APP_NAME = "인플루언서시딩기" if platform.system() in ("Windows", "Darwin") else "InfluencerSeeder"
BASE = Path(SPECPATH)

a = Analysis(
    [str(BASE / "main.py")],
    pathex=[str(BASE)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # selenium core
        "selenium",
        "selenium.webdriver",
        "selenium.webdriver.chrome",
        "selenium.webdriver.chrome.webdriver",
        "selenium.webdriver.chrome.service",
        "selenium.webdriver.chrome.options",
        "selenium.webdriver.remote.webdriver",
        "selenium.webdriver.remote.command",
        "selenium.webdriver.remote.remote_connection",
        "selenium.webdriver.remote.errorhandler",
        "selenium.webdriver.remote.switch_to",
        "selenium.webdriver.remote.mobile",
        "selenium.webdriver.remote.file_detector",
        "selenium.webdriver.common.by",
        "selenium.webdriver.common.keys",
        "selenium.webdriver.common.action_chains",
        "selenium.webdriver.common.actions",
        "selenium.webdriver.common.actions.action_builder",
        "selenium.webdriver.common.actions.pointer_input",
        "selenium.webdriver.common.actions.key_input",
        "selenium.webdriver.common.actions.wheel_input",
        "selenium.webdriver.common.alert",
        "selenium.webdriver.common.desired_capabilities",
        "selenium.webdriver.common.proxy",
        "selenium.webdriver.common.service",
        "selenium.webdriver.common.utils",
        "selenium.webdriver.support.ui",
        "selenium.webdriver.support.expected_conditions",
        "selenium.webdriver.support.wait",
        "selenium.webdriver.support.color",
        "selenium.webdriver.support.select",
        # webdriver-manager
        "webdriver_manager",
        "webdriver_manager.chrome",
        "webdriver_manager.core.driver_cache",
        "webdriver_manager.core.download_manager",
        "webdriver_manager.core.http",
        "webdriver_manager.core.manager",
        "webdriver_manager.core.os_manager",
        # google / gspread
        # PyQt6
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["flask", "flask_cors"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 콘솔창 없음
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",  # Windows 아이콘 (준비 시 주석 해제)
)

# macOS .app 번들
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name=APP_NAME + ".app",
        # icon="assets/icon.icns",  # macOS 아이콘 (준비 시 주석 해제)
        bundle_identifier="com.letscxreer.influencerseeder",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
        },
    )
