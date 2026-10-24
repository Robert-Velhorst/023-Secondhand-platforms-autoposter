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
print(json.dumps({"passed": True, "config_id": identity["config_id"],
                  "os_packages": os_packages, "python_packages": python_packages,
                  "reported_findings": 0, "deployment_acceptance": False}))
