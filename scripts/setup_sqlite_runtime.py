"""Provision only Autoposter's pinned native runtime; never open operator data."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
module_spec = importlib.util.spec_from_file_location("_autoposter_sqlite_setup", ROOT / "app/sqlite_runtime.py")
bootstrap = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(bootstrap)


def build_macos_extension(directory: Path, original: Path, library: Path, spec: dict) -> Path:
    """Build the exact stdlib module when the SDK embeds an older SQLite."""
    release = spec["cpython_source"]
    if tuple(sys.version_info[:3]) != tuple(map(int, release["version"].split("."))):
        raise RuntimeError("The native extension source must match the exact Python release")
    with urllib.request.urlopen(release["url"], timeout=60) as response:
        if not response.url.startswith("https://www.python.org/ftp/python/"):
            raise RuntimeError("Unexpected CPython source origin")
        archive = response.read(48 * 1024 * 1024)
    if len(archive) >= 48 * 1024 * 1024 or hashlib.sha256(archive).hexdigest() != release["sha256"]:
        raise RuntimeError("CPython source archive integrity check failed")
    source_root = directory / "cpython"
    source_root.mkdir()
    prefix = "Python-" + release["version"] + "/"
    total = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:xz") as bundle:
        for member in bundle:
            if not member.name.startswith(prefix):
                continue
            relative = Path(member.name[len(prefix) :])
            wanted = (
                (relative.parts[:1] == ("Include",) and relative.suffix == ".h")
                or (relative.parts[:2] == ("Modules", "_sqlite") and relative.suffix in {".c", ".h"})
                or str(relative) == "LICENSE"
            )
            if not wanted:
                continue
            if not member.isfile() or relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("Unexpected CPython source member")
            total += member.size
            if member.size > 4 * 1024 * 1024 or total > 32 * 1024 * 1024:
                raise RuntimeError("Unexpected CPython source size")
            destination = source_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(bundle.extractfile(member).read())
    sources = [
        source_root / "Modules/_sqlite" / (name + ".c")
        for name in [
            "blob",
            "connection",
            "cursor",
            "microprotocols",
            "module",
            "prepare_protocol",
            "row",
            "statement",
            "util",
        ]
    ]
    if not all(path.is_file() for path in sources):
        raise RuntimeError("The verified CPython source lacks the SQLite module")
    extension = directory / original.name
    # Keep SDK-specific pyconfig.h, exact-version internal headers and the new
    # SQLite header explicit. Link only the adjacent freshly built dylib.
    subprocess.run(
        [
            "cc",
            "-bundle",
            "-undefined",
            "dynamic_lookup",
            "-O2",
            "-fPIC",
            "-arch",
            bootstrap.platform_key().removeprefix("darwin-"),
            "-DPy_BUILD_CORE_MODULE",
            '-DMODULE_NAME="sqlite3"',
            "-I" + sysconfig.get_path("include"),
            "-I" + sysconfig.get_path("platinclude"),
            "-I" + str(source_root / "Include/internal"),
            "-I" + str(source_root / "Modules/_sqlite"),
            "-I" + str(directory),
            *map(str, sources),
            str(library),
            "-o",
            str(extension),
        ],
        check=True,
        timeout=300,
    )
    (directory / "CPython-LICENSE.txt").write_bytes((source_root / "LICENSE").read_bytes())
    return extension


def write_atomic(path: Path, payload: bytes) -> None:
    """Publish a complete artifact inside the already checked runtime directory."""
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".sqlite-", delete=False) as temporary:
        temporary.write(payload)
        temporary.flush()
        os.fsync(temporary.fileno())
        staged = Path(temporary.name)
    try:
        if os.name != "nt":
            staged.chmod(0o644)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def main() -> int:
    spec = json.loads((ROOT / "sqlite-runtime.json").read_text(encoding="utf-8"))
    key = bootstrap.platform_key()
    asset = spec[key]
    target = bootstrap.runtime_layout(spec, key)
    library = target / asset["library"]
    bootstrap.check_runtime_paths(target, library, target / "integrity.json")
    if library.exists():
        if key.startswith("windows") and hashlib.sha256(library.read_bytes()).hexdigest() != asset["binary_sha256"]:
            raise RuntimeError("Existing runtime is not the pinned binary; refusing to overwrite it")
    else:
        with urllib.request.urlopen(asset["url"], timeout=60) as response:
            if not response.url.startswith("https://www.sqlite.org/"):
                raise RuntimeError("Unexpected SQLite download origin")
            archive = response.read(8 * 1024 * 1024)
        if len(archive) >= 8 * 1024 * 1024 or hashlib.sha3_256(archive).hexdigest() != asset["archive_sha3_256"]:
            raise RuntimeError("SQLite archive integrity check failed")
        target.mkdir(parents=True, exist_ok=True)
        if key.startswith("windows"):
            with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                member = bundle.getinfo("sqlite3.dll")
                if member.file_size > 5 * 1024 * 1024:
                    raise RuntimeError("Unexpected native library size")
                binary = bundle.read(member)
            if hashlib.sha256(binary).hexdigest() != asset["binary_sha256"]:
                raise RuntimeError("SQLite binary integrity check failed")
            write_atomic(library, binary)
        else:
            with tempfile.TemporaryDirectory(prefix="autoposter-sqlite-build-") as directory:
                source = Path(directory) / "sqlite3.c"
                with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
                    member = bundle.getmember("sqlite-autoconf-3540100/sqlite3.c")
                    if not member.isfile() or member.size > 20 * 1024 * 1024:
                        raise RuntimeError("Unexpected SQLite source member")
                    source.write_bytes(bundle.extractfile(member).read())
                    if key.startswith("darwin"):
                        header = bundle.getmember("sqlite-autoconf-3540100/sqlite3.h")
                        if not header.isfile() or header.size > 2 * 1024 * 1024:
                            raise RuntimeError("Unexpected SQLite header member")
                        (Path(directory) / "sqlite3.h").write_bytes(bundle.extractfile(header).read())
                output = Path(directory) / asset["library"]
                flags = [
                    "-O2",
                    "-fPIC",
                    "-DSQLITE_THREADSAFE=1",
                    "-DSQLITE_USE_URI=1",
                    "-DSQLITE_ENABLE_COLUMN_METADATA",
                    "-DSQLITE_ENABLE_FTS5",
                    "-DSQLITE_ENABLE_RTREE",
                    "-DSQLITE_ENABLE_DBSTAT_VTAB",
                    "-DSQLITE_ENABLE_MATH_FUNCTIONS",
                ]
                if key.startswith("darwin"):
                    flags += [
                        "-dynamiclib",
                        "-arch",
                        key.removeprefix("darwin-"),
                        "-Wl,-install_name,@rpath/libsqlite3.dylib",
                    ]
                else:
                    flags += ["-shared", "-Wl,-soname,libsqlite3.so.0"]
                subprocess.run(
                    ["cc", *flags, str(source), "-lm", "-ldl", "-pthread", "-o", str(output)], check=True, timeout=300
                )
                extension_metadata = {}
                extension_binary = None
                if key.startswith("darwin"):
                    original, fingerprint = bootstrap.original_sqlite_extension()
                    extension = build_macos_extension(Path(directory), original, output, spec)
                    dependencies = subprocess.check_output(["otool", "-L", str(extension)], text=True).splitlines()[1:]
                    sqlite_dependencies = [
                        line.split(" (", 1)[0].strip()
                        for line in dependencies
                        if "sqlite3" in line.lower() and ".dylib (" in line
                    ]
                    if len(sqlite_dependencies) != 1:
                        raise RuntimeError("The macOS SQLite extension must have one relocatable SQLite dependency")
                    subprocess.run(
                        [
                            "install_name_tool",
                            "-change",
                            sqlite_dependencies[0],
                            "@loader_path/" + asset["library"],
                            str(extension),
                        ],
                        check=True,
                        timeout=60,
                    )
                    for binary_path in [output, extension]:
                        subprocess.run(
                            ["codesign", "--force", "--sign", "-", "--timestamp=none", str(binary_path)],
                            check=True,
                            timeout=60,
                        )
                    extension_binary = extension.read_bytes()
                    extension_metadata = {
                        "extension_name": original.name,
                        "original_extension_sha256": fingerprint,
                        "extension_sha256": hashlib.sha256(extension_binary).hexdigest(),
                        "python_abi": sysconfig.get_config_var("SOABI"),
                        "python_version": ".".join(map(str, sys.version_info[:3])),
                        "original_sqlite_dependency": sqlite_dependencies[0],
                        "extension_build": "verified CPython stdlib source with selected SDK headers",
                        "cpython_source_sha256": spec["cpython_source"]["sha256"],
                    }
                    license_binary = (Path(directory) / "CPython-LICENSE.txt").read_bytes()
                binary = output.read_bytes()
                compiler = subprocess.check_output(["cc", "--version"], text=True).splitlines()[0]
            provenance = (
                json.dumps(
                    {
                        "version": spec["version"],
                        "source_sha3_256": asset["archive_sha3_256"],
                        "binary_sha256": hashlib.sha256(binary).hexdigest(),
                        "compiler": compiler,
                        "flags": flags,
                        **extension_metadata,
                    },
                    indent=2,
                )
                + "\n"
            )
            write_atomic(target / "integrity.json", provenance.encode("utf-8"))
            if extension_binary is not None:
                write_atomic(target / extension_metadata["extension_name"], extension_binary)
                write_atomic(target / "CPython-LICENSE.txt", license_binary)
            write_atomic(library, binary)
    # Fresh process: no replacing an already initialized sqlite3 binding.
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from app.sqlite_runtime import runtime_evidence; print(json.dumps(runtime_evidence()))",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
