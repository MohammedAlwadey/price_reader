# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

PROJECT_DIR = Path.cwd()

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
hiddenimports += collect_submodules("pricing")
hiddenimports += collect_submodules("config")

hiddenimports += [
    "pricing",
    "pricing.apps",
    "pricing.models",
    "pricing.views",
    "pricing.urls",
    "pricing.forms",
    "pricing.admin",
    "pricing.session_middleware",
    "pricing.services",
    "pricing.services.oracle_client",
    "pricing.migrations",
    "pricing.migrations.0001_initial",
    "pricing.migrations.0002_remove_oraclesettings_name_and_more",
    "pricing.migrations.0003_activeusersession",
    "pricing.migrations.0004_userloginpolicy",
    "config",
    "config.settings",
    "config.urls",
    "config.wsgi",
    "whitenoise",
    "whitenoise.middleware",
    "whitenoise.storage",
    "waitress",
    "dotenv",
]

datas = []
datas += collect_data_files("pricing", include_py_files=False)
datas += [
    ("pricing/templates", "pricing/templates"),
    ("pricing/static", "pricing/static"),
    ("templates", "templates"),
    ("staticfiles", "staticfiles"),
]

a = Analysis(
    ["run_client.py"],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["sslserver"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PriceReader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PriceReader",
)