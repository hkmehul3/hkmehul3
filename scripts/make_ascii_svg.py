#!/usr/bin/env python3
"""Turn a prepared grayscale portrait into a monochrome ASCII-art SVG.

The SVG types itself in line by line, terminal style, and holds the final
frame. Every glyph is real text in a <text> element, so it stays crisp at
any zoom and copies out as characters.

    python3 scripts/make_ascii_svg.py assets/portrait.png -o ascii-portrait.svg
"""
from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image

# Dense -> sparse. The image is inverted before mapping, so dark pixels of
# the photo land on the dense end of this ramp.
RAMP = "@%#*+=-:. "

BG = "#0d1117"
INK = "#c9d1d9"
DIM = "#6e7681"
ACCENT = "#22d3ee"


def image_to_rows(path: Path, cols: int, aspect: float, gamma: float,
                  floor: float, ceil: float, equalize: bool,
                  bg_cut: float) -> list[str]:
    """Sample the image into a character grid.

    The art is rendered as light glyphs on a dark panel, so glyph density
    reads as brightness: bright pixels get the dense end of the ramp and
    dark pixels fade to spaces. The prepared image has its background
    knocked to black, which therefore renders as empty space.
    """
    im = Image.open(path).convert("L")
    rows = max(1, int(im.height / im.width * cols * aspect))
    im = im.resize((cols, rows), Image.LANCZOS)

    a = np.asarray(im, dtype=np.float32) / 255.0
    subject = a > bg_cut

    if equalize and subject.any():
        # Downsampling to ~90 columns compresses the histogram badly;
        # rank-equalising the subject's own tones is what keeps the whole
        # ramp in play instead of collapsing onto two or three glyphs.
        vals = np.sort(a[subject])
        ranks = np.searchsorted(vals, a[subject], side="left") / max(1, len(vals) - 1)
        a = np.zeros_like(a)
        a[subject] = np.clip(ranks, 0.0, 1.0)
    else:
        a = np.clip((a - floor) / max(1e-6, ceil - floor), 0.0, 1.0)

    a = a ** gamma
    a[~subject] = 0.0
    idx = np.clip(((1.0 - a) * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)

    out = ["".join(RAMP[i] for i in row) for row in idx]
    return [r.rstrip() for r in out]


def build_svg(rows: list[str], cols: int, char_w: float, line_h: float,
              pad: int, total: float, hold: float, label: str) -> str:
    n = len(rows)
    width = int(cols * char_w + pad * 2)
    height = int(n * line_h + pad * 2 + line_h * 2.2)

    # Each line wipes in from the left; lines are staggered so the portrait
    # resolves top to bottom like a terminal drawing itself.
    step = total / max(1, n)
    cycle = total + hold

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">',
        "<defs>",
        '<style><![CDATA[',
        f'.bg{{fill:{BG}}}',
        f'text{{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;'
        f'font-size:{char_w / 0.6:.2f}px;fill:{INK};white-space:pre;'
        f'dominant-baseline:hanging}}',
        f'.cap{{fill:{DIM};font-size:{char_w / 0.6 * 0.95:.2f}px}}',
        f'.cap tspan{{fill:{ACCENT}}}',
        ']]></style>',
        "</defs>",
        f'<rect class="bg" width="{width}" height="{height}" rx="10"/>',
    ]

    for i, row in enumerate(rows):
        if not row:
            continue
        y = pad + i * line_h
        begin = i * step
        # clip rect grows left -> right for this one line
        cid = f"c{i}"
        parts.append(
            f'<clipPath id="{cid}"><rect x="{pad}" y="{y - 2:.1f}" '
            f'height="{line_h + 4:.1f}" width="{cols * char_w:.1f}">'
            f'<animate attributeName="width" values="0;{cols * char_w:.1f};'
            f'{cols * char_w:.1f}" keyTimes="0;{step * 1.6 / cycle:.4f};1" '
            f'begin="{begin:.3f}s" dur="{cycle:.3f}s" repeatCount="indefinite" '
            f'fill="freeze"/></rect></clipPath>'
        )
        # textLength pins the run to an exact width, so the art keeps its
        # proportions no matter which monospace font the viewer resolves.
        parts.append(
            f'<g clip-path="url(#{cid})"><text x="{pad}" y="{y:.1f}" '
            f'textLength="{len(row) * char_w:.1f}" lengthAdjust="spacingAndGlyphs">'
            f'{escape(row)}</text></g>'
        )

    cy = pad + n * line_h + line_h * 0.6
    parts.append(
        f'<text class="cap" x="{pad}" y="{cy:.1f}">'
        f'<tspan>&#9646;</tspan> {escape(label)}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("ascii-portrait.svg"))
    ap.add_argument("--cols", type=int, default=86)
    ap.add_argument("--aspect", type=float, default=0.50,
                    help="row height / column width of the glyph cell")
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--floor", type=float, default=0.05)
    ap.add_argument("--ceil", type=float, default=0.95)
    ap.add_argument("--char-w", type=float, default=4.3)
    ap.add_argument("--line-h", type=float, default=7.4)
    ap.add_argument("--pad", type=int, default=16)
    ap.add_argument("--dur", type=float, default=3.2)
    ap.add_argument("--hold", type=float, default=11.0)
    ap.add_argument("--label", default="")
    ap.add_argument("--txt", type=Path, help="also dump the raw ASCII here")
    ap.add_argument("--equalize", action="store_true",
                    help="rank-equalise subject tones across the ramp")
    ap.add_argument("--bg-cut", type=float, default=0.02,
                    help="cells at or below this brightness count as background")
    args = ap.parse_args()

    rows = image_to_rows(args.src, args.cols, args.aspect, args.gamma,
                         args.floor, args.ceil, args.equalize, args.bg_cut)
    if args.txt:
        args.txt.write_text("\n".join(rows) + "\n")

    svg = build_svg(rows, args.cols, args.char_w, args.line_h, args.pad,
                    args.dur, args.hold, args.label)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg)
    print(f"wrote {args.out} ({len(rows)} rows x {args.cols} cols)")


if __name__ == "__main__":
    main()
