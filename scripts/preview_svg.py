#!/usr/bin/env python3
"""Render an animated SVG's final frame to PNG so it can be eyeballed."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import cairosvg

src = Path(sys.argv[1])
dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".png")
scale = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0

s = src.read_text()
# Freeze every reveal animation at its end state.
s = re.sub(r'<rect([^>]*?)width="0"', r'<rect\1width="99999"', s)
s = re.sub(r'<animate[^>]*/>', "", s)
s = re.sub(r'<animate.*?</animate>', "", s, flags=re.S)
tmp = src.with_name(src.stem + ".static.svg")
tmp.write_text(s)
cairosvg.svg2png(url=str(tmp), write_to=str(dst), scale=scale)
tmp.unlink()
print(f"wrote {dst}")
