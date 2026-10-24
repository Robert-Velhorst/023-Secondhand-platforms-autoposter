"""Require a complete exact-image inventory with no suppressed findings."""

import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
scan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
identity = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert identity["verified_descriptor_chain"] is True
assert scan["SchemaVersion"] == 2 and scan["ArtifactType"] == "container_image"
assert scan["Metadata"]["ImageID"] == identity["config_id"]
assert scan["Metadata"]["OS"]["Family"] == "alpine"
assert scan["Metadata"]["OS"]["Name"] == "3.24.3"
assert scan["Metadata"]["OS"].get("EOSL", False) is False
assert scan["Results"]
installed = {}
os_packages = 0
python_packages = 0
for result in scan["Results"]:
    assert result["Packages"]
    for field in ["Vulnerabilities", "ExperimentalModifiedFindings"]:
        assert not result.get(field), "Unresolved or modified findings: " + field
    if result["Class"] == "os-pkgs":
        assert result["Type"] == "alpine"
        os_packages += len(result["Packages"])
    if result["Type"] == "python-pkg":
        python_packages += len(result["Packages"])
    for package in result["Packages"]:
        name = re.sub(r"[-_.]+", "-", package["Name"].lower())
        installed.setdefault(name, set()).add(package["Version"])
assert os_packages and python_packages
for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    declaration = re.fullmatch(r"([\w.-]+)(?:\[[\w,.-]+\])?==([\w.+-]+)", line)
    assert declaration, "Runtime requirements must be exactly pinned"
    name = re.sub(r"[-_.]+", "-", declaration[1].lower())
    assert declaration[2] in installed.get(name, set()), "Installed direct version mismatch: " + name
assert installed.get("sqlite-libs") == {"3.54.1-r0"}
assert installed.get("libpq") == {"18.6-r0"}
assert installed.get("libcrypto4") == {"4.1.0-r0"}
assert installed.get("libssl4") == {"4.1.0-r0"}
assert installed.get("psycopg-c") == {"3.3.6"}
assert not installed.get("psycopg-binary"), "The Linux image must not retain the old vendored client"
declared = {
    line for line in (root / "requirements.txt").read_text().splitlines() if line.strip() and not line.startswith("#")
}
image_declared = {
    line.replace("psycopg[c]", "psycopg[binary]")
    for line in (root / "requirements-image.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
}
assert declared == image_declared, "Image and application dependency versions diverged"
qualification = {
    line
    for line in (root / "requirements-qualification.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
}
development_pytest = {
    line for line in (root / "requirements-dev.txt").read_text().splitlines() if line.startswith("pytest==")
}
assert qualification == development_pytest, "CI tools must retain the existing development pytest version"
print(
    json.dumps(
        {
            "passed": True,
            "config_id": identity["config_id"],
            "os_packages": os_packages,
            "python_packages": python_packages,
            "reported_findings": 0,
            "deployment_acceptance": False,
        }
    )
)
