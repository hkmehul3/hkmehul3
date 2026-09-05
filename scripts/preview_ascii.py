#!/usr/bin/env python3
"""Render an ASCII dump to PNG with a real monospace font.

Browsers honour the SVG's textLength, so this is a closer preview of the
published art than a headless SVG rasteriser (which quietly substitutes
fonts and ignores textLength).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"

src = Path(sys.argv[1])
dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".png")
size = int(sys.argv[3]) if len(sys.argv) > 3 else 12

rows = src.read_text().splitlines()
font = ImageFont.truetype(FONT, size)
cw = font.getlength("M")
lh = size * 1.16
w = int(max((len(r) for r in rows), default=1) * cw) + 24
h = int(len(rows) * lh) + 24

im = Image.new("RGB", (w, h), "#0d1117")
d = ImageDraw.Draw(im)
for i, r in enumerate(rows):
    d.text((12, 12 + i * lh), r, font=font, fill="#c9d1d9")
im.save(dst)
print(f"wrote {dst} {im.size} cell={cw:.2f}x{lh:.2f}")
