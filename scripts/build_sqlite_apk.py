"""Package the verified current library without breaking Alpine dependencies."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = json.loads((ROOT / "sqlite-runtime.json").read_text(encoding="utf-8"))
architecture = subprocess.check_output(["apk", "--print-arch"], text=True).strip()
profile = {"x86_64": "linux-x86_64", "aarch64": "linux-arm64"}[architecture]
target = ROOT / ".autoposter-runtime/sqlite" / spec["version"] / profile
library = target / spec[profile]["library"]
provenance = json.loads((target / "integrity.json").read_text(encoding="utf-8"))
digest = hashlib.sha256(library.read_bytes()).hexdigest()
if digest != provenance["binary_sha256"] or provenance["source_sha3_256"] != spec[profile]["archive_sha3_256"]:
    raise RuntimeError("Only the verified SQLite build can be packaged")
evidence = json.loads(
    subprocess.check_output(
        [
            sys.executable,
            "-c",
            "import json; from app.sqlite_runtime import runtime_evidence; print(json.dumps(runtime_evidence()))",
        ],
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        text=True,
    )
)
if evidence["version"] != spec["version"] or evidence["binary_sha256"] != digest:
    raise RuntimeError("The packaged library must be the qualified active engine")
# This key authenticates only this build's verified local artifact. The private
# key stays in the builder; runtime uses the public key only for offline install.
key = Path("/tmp/autoposter-sqlite-build.rsa")
keys = Path("/tmp/autoposter-package-keys")
keys.mkdir()
subprocess.run(
    ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:3072", "-out", str(key)],
    check=True,
    timeout=60,
)
key.chmod(0o600)
subprocess.run(
    ["openssl", "rsa", "-in", str(key), "-pubout", "-out", str(keys / "autoposter-sqlite-build.rsa.pub")],
    check=True,
    timeout=60,
)
with tempfile.TemporaryDirectory(prefix="autoposter-sqlite-apk-") as temporary:
    package = Path(temporary)
    package.chmod(0o755)
    destination = package / "usr/lib/libsqlite3.so.0"
    destination.parent.mkdir(parents=True)
    shutil.copyfile(library, destination)
    destination.chmod(0o644)
    documentation = package / "usr/share/doc/sqlite-libs"
    documentation.mkdir(parents=True)
    (documentation / "autoposter-build.json").write_text(
        json.dumps({"runtime": evidence, "build": provenance}, indent=2) + "\n", encoding="utf-8"
    )
    (documentation / "copyright").write_text(
        "SQLite is in the public domain.\n"
        "Upstream: https://www.sqlite.org/copyright.html\n"
        f"Verified source: {spec[profile]['url']}\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "apk",
            "--sign-key",
            str(key),
            "mkpkg",
            "--files",
            str(package),
            "--info",
            "name:sqlite-libs",
            "--info",
            "version:" + spec["version"] + "-r0",
            "--info",
            "arch:" + architecture,
            "--info",
            "origin:sqlite",
            "--info",
            "description:Autoposter build of checksum-verified upstream SQLite",
            "--info",
            "license:blessing",
            "--info",
            "maintainer:Secondhand Platforms Autoposter",
            "--info",
            "url:https://www.sqlite.org/",
            "--info",
            "depends:musl",
            "--info",
            "provides:so:libsqlite3.so.0=0",
            "--output",
            "/tmp/autoposter-sqlite.apk",
        ],
        check=True,
        timeout=60,
    )
subprocess.run(["apk", "--keys-dir", str(keys), "verify", "/tmp/autoposter-sqlite.apk"], check=True, timeout=60)

key.unlink()  # The private build key never enters a committed image layer.
