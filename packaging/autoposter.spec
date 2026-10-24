import hashlib
import json
import sysconfig
from pathlib import Path

project_root = Path(SPEC).resolve().parent.parent
native_spec = json.loads((project_root / "sqlite-runtime.json").read_text(encoding="utf-8"))
native_key = {"win-amd64": "windows-x86_64", "win-arm64": "windows-arm64"}[sysconfig.get_platform().lower()]
native_relative = Path(".autoposter-runtime/sqlite") / native_spec["version"] / native_key / "sqlite3.dll"
native = project_root / native_relative
if hashlib.sha256(native.read_bytes()).hexdigest() != native_spec[native_key]["binary_sha256"]:
    raise RuntimeError("Provision the verified project-local SQLite DLL before packaging")

hidden_imports = [
    "sqlalchemy.dialects.sqlite.pysqlite",
    "uvicorn.lifespan.off",
    "uvicorn.lifespan.on",
    "uvicorn.logging",
    "uvicorn.loops.asyncio",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
]

analysis = Analysis(
    [str(project_root / "app" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[(str(native), native_relative.parent.as_posix())],
    datas=[
        (str(project_root / "public"), "public"),
        (str(project_root / "migrations"), "migrations"),
        (str(project_root / "alembic.ini"), "."),
        (str(project_root / "sqlite-runtime.json"), "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[str(project_root / "scripts/sqlite_pyinstaller_hook.py")],
    excludes=["pytest", "ruff", "tkinter"],
    noarchive=False,
)

# The verified nested DLL is preloaded by the runtime hook; omit the older
# SDK library that PyInstaller would otherwise collect at the archive root.
analysis.binaries = [entry for entry in analysis.binaries if entry[0].lower() != "sqlite3.dll"]

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="SecondhandAutoposter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
