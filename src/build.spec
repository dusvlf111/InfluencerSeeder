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
    datas=[
        (str(BASE / "assets"), "assets"),
    ],
    hiddenimports=[
        # PyQt6 (수집은 임베디드 QtWebEngine 브라우저에서 JS 로 — Selenium 미사용)
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtNetwork",
        "PyQt6.sip",
        # PyQt6 WebEngine (embedded Instagram browser). These are imported
        # behind a try/except in ui.main_window, so list them explicitly or
        # PyInstaller won't bundle QtWebEngineProcess + its resources.
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["flask", "flask_cors"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ── onedir build ────────────────────────────────────────────────────────────
# QtWebEngine (the embedded browser) does NOT work with PyInstaller's onefile
# mode: QtWebEngineProcess.exe and the ICU/locale resources must live on disk,
# not be unpacked to a temp dir at launch. So the EXE carries only the scripts
# (exclude_binaries=True) and COLLECT gathers binaries/data into an app folder.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # 콘솔창 없음
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BASE / "assets" / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

# macOS .app 번들 (onedir COLLECT 를 감싼다)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=APP_NAME + ".app",
        icon=str(BASE / "assets" / "icon.icns"),
        bundle_identifier="com.letscxreer.influencerseeder",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
        },
    )
