from __future__ import annotations

import subprocess
import sys


def main() -> int:
    for requirements in (
        "requirements.lock.txt", "requirements-dev.lock.txt",
        "requirements-build.lock.txt", "requirements-audit.lock.txt",
    ):
        command = [
            sys.executable, "-m", "pip_audit", "--requirement", requirements,
            "--strict", "--disable-pip", "--require-hashes",
        ]
        print(f"==> dependency-audit: {' '.join(command)}", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            print(f"Dependency audit failed for {requirements}.", file=sys.stderr)
            return result.returncode
        print(f"Dependency audit passed for {requirements}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
