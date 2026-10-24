from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    command: list[str]


CHECKS = [
    Check(
        "lint", [sys.executable, "-m", "ruff", "check", "app", "tests", "migrations", "scripts", "runtime_bootstrap"]
    ),
    Check("compile", [sys.executable, "-m", "compileall", "app", "tests", "migrations", "runtime_bootstrap"]),
    Check("tests", [sys.executable, "-m", "pytest"]),
    Check("doctor", [sys.executable, "-m", "app.doctor", "--json"]),
]


def main() -> int:
    temp_dir = Path(".tmp/verify") / f"run-{os.getpid()}"
    temp_dir = temp_dir.resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"TMP": str(temp_dir), "TEMP": str(temp_dir), "TMPDIR": str(temp_dir)})

    for check in CHECKS:
        print(f"==> {check.name}: {' '.join(check.command)}", flush=True)
        result = subprocess.run(check.command, check=False, env=env)
        if result.returncode != 0:
            print(f"Verification failed during {check.name}.", file=sys.stderr)
            return result.returncode
    print("Verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
