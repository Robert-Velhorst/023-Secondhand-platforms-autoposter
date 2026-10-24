"""Load Autoposter's verified, project-local SQLite before any ledger is opened.

No network, downloads, database files, environment-selected library paths or
global interpreter installation changes occur here. Provisioning is separate.
"""

from __future__ import annotations

import ctypes
import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
import os
import sys
import sysconfig
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
_handle = None
_verified = False
_identity = None
_sdk_extension = None


def platform_key() -> str:
    if sys.maxsize <= 2**32:
        raise RuntimeError("Autoposter's verified SQLite runtime requires a 64-bit interpreter")
    # Windows platform.machine() depends on inherited processor environment
    # variables. Select the DLL by the interpreter's compiled ABI instead.
    if os.name == "nt" and sysconfig.get_platform().lower() == "win-amd64":
        return "windows-x86_64"
    if os.name == "nt" and sysconfig.get_platform().lower() == "win-arm64":
        return "windows-arm64"
    if sys.platform == "linux" and os.uname().machine.lower() == "x86_64":
        return "linux-x86_64"
    if sys.platform == "linux" and os.uname().machine.lower() in {"aarch64", "arm64"}:
        return "linux-arm64"
    if sys.platform == "darwin" and os.uname().machine.lower() in {"arm64", "x86_64"}:
        return "darwin-" + os.uname().machine.lower()
    raise RuntimeError("Autoposter's verified SQLite runtime has no supported native profile for this interpreter")


def original_sqlite_extension():
    global _sdk_extension
    if _sdk_extension is None:
        module = importlib.util.find_spec("_sqlite3")
        if module is None or not isinstance(module.loader, importlib.machinery.ExtensionFileLoader):
            raise RuntimeError("The macOS profile requires a CPython SQLite extension")
        original = Path(module.origin).resolve()
        if not original.is_relative_to(Path(sys.base_prefix).resolve()):
            raise RuntimeError("The SQLite extension is outside the selected CPython installation")
        _sdk_extension = (original, hashlib.sha256(original.read_bytes()).hexdigest())
    return _sdk_extension


def runtime_layout(spec: dict, key: str):
    target = ROOT / ".autoposter-runtime" / "sqlite" / spec["version"] / key
    if key.startswith("darwin"):
        _, fingerprint = original_sqlite_extension()
        version = ".".join(map(str, sys.version_info[:3]))
        target /= "python-" + version + "-" + fingerprint[:16]
    return target


def check_runtime_paths(target: Path, *files: Path):
    if not target.is_relative_to(ROOT) or not target.resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError("Native runtime target leaves the project")
    paths = [*files, target]
    for parent in target.parents:
        if parent == ROOT:
            break
        paths.append(parent)
    for path in paths:
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise RuntimeError("Linked SQLite runtime paths are not accepted")


def require_stable_sqlite():
    global _handle, _verified, _identity
    if _verified:
        return sys.modules["sqlite3"]
    if "sqlite3" in sys.modules or "_sqlite3" in sys.modules:
        raise RuntimeError("SQLite was initialized before Autoposter's verified bootstrap")
    spec = json.loads((ROOT / "sqlite-runtime.json").read_text(encoding="utf-8"))
    expected_python = tuple(map(int, spec["cpython_source"]["version"].split(".")))
    if tuple(sys.version_info[:3]) != expected_python:
        raise RuntimeError("The verified runtime requires CPython " + spec["cpython_source"]["version"])
    key = platform_key()
    target = runtime_layout(spec, key)
    library = target / spec[key]["library"]
    check_runtime_paths(target, library, target / "integrity.json")
    if not library.is_file():
        raise RuntimeError("Verified SQLite runtime missing; run scripts/setup_sqlite_runtime.py")
    digest = hashlib.sha256(library.read_bytes()).hexdigest()
    if key.startswith("windows"):
        expected = spec[key]["binary_sha256"]
    else:
        provenance = json.loads((target / "integrity.json").read_text(encoding="utf-8"))
        if (
            provenance.get("source_sha3_256") != spec[key]["archive_sha3_256"]
            or provenance.get("version") != spec["version"]
        ):
            raise RuntimeError("SQLite build provenance does not match the pinned release")
        expected = provenance.get("binary_sha256")
    if not expected or digest != expected:
        raise RuntimeError("SQLite runtime integrity check failed")
    if os.name == "nt":
        _handle = ctypes.WinDLL(str(library))
    elif key.startswith("darwin"):
        original, fingerprint = original_sqlite_extension()
        extension = target / original.name
        check_runtime_paths(target, extension)
        if (
            provenance.get("original_extension_sha256") != fingerprint
            or provenance.get("cpython_source_sha256") != spec["cpython_source"]["sha256"]
            or provenance.get("python_abi") != sysconfig.get_config_var("SOABI")
            or hashlib.sha256(extension.read_bytes()).hexdigest() != provenance.get("extension_sha256")
        ):
            raise RuntimeError("The project-local CPython SQLite extension failed integrity or ABI validation")
        module_spec = importlib.util.spec_from_file_location("_sqlite3", extension)
        if module_spec is None or module_spec.loader is None:
            raise RuntimeError("The verified SQLite extension cannot be loaded")
        _handle = importlib.util.module_from_spec(module_spec)
        sys.modules["_sqlite3"] = _handle
        module_spec.loader.exec_module(_handle)
    else:
        _handle = ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL)
    sqlite = importlib.import_module("sqlite3")
    with sqlite.connect(":memory:") as connection:
        actual = connection.execute("SELECT sqlite_version()").fetchone()[0]
        source_id = connection.execute("SELECT sqlite_source_id()").fetchone()[0]
        options = [row[0] for row in connection.execute("PRAGMA compile_options")]
    connection.close()
    if actual != spec["version"] or "THREADSAFE=1" not in options:
        raise RuntimeError("Loaded SQLite version or thread-safety policy is incorrect")
    _identity = {
        "version": actual,
        "source_id": source_id,
        "binary_sha256": digest,
        "platform": key,
        "compile_options": options,
    }
    _verified = True
    return sqlite


def runtime_evidence() -> dict:
    require_stable_sqlite()
    return dict(_identity)
