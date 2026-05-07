#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
import zipfile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    repo_root = Path.cwd()
    result = subprocess.run([sys.executable, "-m", "build"], cwd=repo_root, text=True, capture_output=True, check=False)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        return result.returncode
    wheel = next((repo_root / "dist").glob("*.whl"), None)
    if wheel is None:
        print("wheel not produced", file=sys.stderr)
        return 1
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        if not any(name.endswith("entry_points.txt") for name in names):
            print("missing entry_points.txt", file=sys.stderr)
            return 1
        for forbidden in [".build", ".venv", ".git", "model", "debug-bundle"]:
            if any(forbidden in name for name in names):
                print(f"forbidden content in wheel: {forbidden}", file=sys.stderr)
                return 1
    if args.output:
        args.output.write_text(str(wheel), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
