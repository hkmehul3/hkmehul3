#!/usr/bin/env python3
"""Rebuild every generated asset in this repo.

    python3 scripts/build.py             # everything
    python3 scripts/build.py --skip-photo  # leave the ASCII portrait alone
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*cmd: str) -> None:
    print("+", " ".join(cmd))
    subprocess.run([sys.executable, *cmd], cwd=ROOT, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-photo", action="store_true")
    ap.add_argument("--skip-contrib", action="store_true")
    args = ap.parse_args()

    p = json.loads((ROOT / "profile.json").read_text())
    port = p.get("portrait", {})

    if not args.skip_photo:
        crop = [str(v) for v in port.get("crop", [0, 0, 1, 1])]
        run("scripts/prep_photo.py", "assets/photo.jpg", "--crop", *crop,
            "-o", "assets/portrait.png")
        run("scripts/make_ascii_svg.py", "assets/portrait.png",
            "--cols", str(port.get("cols", 88)),
            "--aspect", "0.575", "--char-w", "4.6", "--line-h", "8.0",
            "--gamma", str(port.get("gamma", 0.8)),
            "--floor", str(port.get("floor", 0.04)), "--ceil", "1.0",
            "--label", f"{p['username']}.jpg -> ascii",
            "-o", "ascii-portrait.svg")

    run("scripts/make_info_card.py")

    if not args.skip_contrib:
        run("scripts/make_contrib_svg.py", "--cache", "assets/contrib-cache.json")

    run("scripts/make_readme.py")
    print("\nall assets rebuilt")


if __name__ == "__main__":
    main()
