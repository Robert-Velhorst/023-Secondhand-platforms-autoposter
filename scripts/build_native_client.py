"""Build pinned client libraries in a disposable Linux image stage.

No database server is built, started or contacted. The selected prefix must be
absent; this command never replaces the host SDK or system crypto libraries.
"""

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "native-client-runtime.json").read_text(encoding="utf-8"))
PREFIX = Path(SPEC["prefix"])


def run(command, cwd, env=None):
    subprocess.run(command, cwd=cwd, env=env, check=True, timeout=1200)


def source_archive(component, directory):
    archive = directory / (component["version"] + ".archive")
    digest = hashlib.sha256()
    size = 0
    with urlopen(component["url"], timeout=60) as response, archive.open("xb") as output:
        if not response.url.startswith("https://"):
            raise RuntimeError("Native sources must use HTTPS")
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > 100 * 1024 * 1024:
                raise RuntimeError("Native source archive exceeds its download limit")
            digest.update(chunk)
            output.write(chunk)
    if digest.hexdigest() != component["sha256"]:
        raise RuntimeError("Native source archive checksum mismatch")
    destination = directory / "source"
    destination.mkdir()
    with tarfile.open(archive) as source:
        members = source.getmembers()
        if len(members) > 50000 or sum(item.size for item in members) > 1024**3:
            raise RuntimeError("Native source archive exceeds its extraction limit")
        source.extractall(destination, filter="data")
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir() or roots[0].is_symlink():
        raise RuntimeError("Native archive must contain one source directory")
    return roots[0]


def main():
    if sys.platform != "linux" or SPEC["schema_version"] != 1:
        raise RuntimeError("This source builder supports disposable Linux image stages only")
    if PREFIX != Path("/opt/autoposter-native") or PREFIX.exists():
        raise RuntimeError("Native installation requires the absent dedicated prefix")
    environment = dict(os.environ)
    environment["CPPFLAGS"] = f"-I{PREFIX}/include"
    environment["LDFLAGS"] = f"-L{PREFIX}/lib -Wl,-rpath,{PREFIX}/lib"
    environment["LD_LIBRARY_PATH"] = str(PREFIX / "lib")
    environment["PKG_CONFIG_PATH"] = str(PREFIX / "lib/pkgconfig")
    with tempfile.TemporaryDirectory(prefix="autoposter-native-source-") as temporary:
        workspace = Path(temporary)
        openssl_work = workspace / "openssl"
        openssl_work.mkdir()
        openssl_source = source_archive(SPEC["openssl"], openssl_work)
        run(
            ["perl", "Configure", f"--prefix={PREFIX}", "--libdir=lib", "--openssldir=/etc/ssl", "shared", "no-tests"],
            openssl_source,
        )
        run(["make", "-j2"], openssl_source)
        run(["make", "install_sw"], openssl_source)
        postgres_work = workspace / "postgresql"
        postgres_work.mkdir()
        postgres_source = source_archive(SPEC["postgresql"], postgres_work)
        run(
            [
                "./configure",
                f"--prefix={PREFIX}",
                "--with-ssl=openssl",
                "--without-readline",
                "--without-zlib",
                "--without-icu",
                "--with-gssapi",
                "--with-ldap",
            ],
            postgres_source,
            environment,
        )
        # Build only the shared client and its compile-time prerequisites.
        run(["make", "-C", "src/port", "-j2"], postgres_source, environment)
        run(["make", "-C", "src/common", "-j2"], postgres_source, environment)
        run(["make", "-C", "src/interfaces/libpq", "-j2"], postgres_source, environment)
        for target in ["src/interfaces/libpq", "src/include", "src/bin/pg_config"]:
            run(["make", "-C", target, "install"], postgres_source, environment)
        licenses = PREFIX / "share/licenses"
        licenses.mkdir(parents=True)
        shutil.copyfile(openssl_source / "LICENSE.txt", licenses / "OpenSSL.txt")
        shutil.copyfile(postgres_source / "COPYRIGHT", licenses / "PostgreSQL.txt")
    # Version-only native calls; neither opens a socket or a database.
    crypto = ctypes.CDLL(str(PREFIX / "lib/libcrypto.so.4"))
    crypto.OpenSSL_version.argtypes = [ctypes.c_int]
    crypto.OpenSSL_version.restype = ctypes.c_char_p
    actual_ssl = crypto.OpenSSL_version(0).decode("ascii")
    if not actual_ssl.startswith("OpenSSL " + SPEC["openssl"]["version"] + " "):
        raise RuntimeError("Compiled OpenSSL version does not match the pinned source")
    # Loading the dependent libssl first also proves it resolves the pinned
    # major-4 crypto library in this builder process.
    ctypes.CDLL(str(PREFIX / "lib/libssl.so.4"), mode=ctypes.RTLD_GLOBAL)
    pq = ctypes.CDLL(str(PREFIX / "lib/libpq.so.5"))
    pq.PQlibVersion.restype = ctypes.c_int
    if pq.PQlibVersion() != 180006:
        raise RuntimeError("Compiled libpq must report PostgreSQL 18.6")
    libraries = {}
    for item in sorted((PREFIX / "lib").rglob("*")):
        if item.is_file() and not item.is_symlink() and ".so" in item.name:
            libraries[str(item.relative_to(PREFIX))] = hashlib.sha256(item.read_bytes()).hexdigest()
    if not libraries:
        raise RuntimeError("No compiled shared libraries were produced")
    (PREFIX / "share/build-provenance.json").write_text(
        json.dumps(
            {
                "sources": SPEC,
                "openssl": actual_ssl,
                "libpq": pq.PQlibVersion(),
                "libraries": libraries,
                "database_connected": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Only shared libraries and provenance enter the final image. Compilers,
    # headers, static archives and pg_config stay in this disposable stage.
    runtime = Path("/native-runtime")
    if runtime.exists():
        raise RuntimeError("The runtime export destination must be absent")
    shutil.copytree(PREFIX / "lib", runtime / "lib", symlinks=True, ignore=shutil.ignore_patterns("*.a", "pkgconfig"))
    shutil.copytree(PREFIX / "share", runtime / "share", symlinks=True)


if __name__ == "__main__":
    main()
