#!/usr/bin/env python3
"""Render the neofetch-style info panel that sits beside the ASCII portrait.

Reads profile.json, writes info-card.svg. Rows fade in one after another so
the panel fills itself in like a command printing its output.

    python3 scripts/make_info_card.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from theme import ACCENT, BORDER, DIM, FAINT, INK, LEVELS, MONO, PANEL, WARM

PAD = 22
SIZE = 13.0
LINE = 21.0
KEY_W = 96.0


def rows_svg(profile: dict) -> tuple[list[str], float]:
    """Build the body of the card and report the height it needs."""
    out: list[str] = []
    y = PAD + SIZE + 6
    step = 0.10  # stagger between rows, in seconds
    n = 0

    def anim(delay: float) -> str:
        return (f'<animate attributeName="opacity" values="0;0;1" '
                f'keyTimes="0;{delay / 6.0:.4f};{min(0.999, (delay + 0.35) / 6.0):.4f}" '
                f'dur="6s" begin="0s" fill="freeze"/>')

    head = profile.get("prompt", "you@github")
    out.append(
        f'<g opacity="1"><text x="{PAD}" y="{y:.1f}" font-size="{SIZE + 1:.1f}" '
        f'font-weight="700" fill="{ACCENT}">{escape(head)}</text>{anim(0)}</g>'
    )
    y += LINE * 0.78
    out.append(
        f'<g opacity="1"><text x="{PAD}" y="{y:.1f}" font-size="{SIZE:.1f}" '
        f'fill="{FAINT}">{"-" * 34}</text>{anim(step)}</g>'
    )
    y += LINE
    n = 2

    for key, value in profile.get("info", []):
        out.append(
            f'<g opacity="1">'
            f'<text x="{PAD}" y="{y:.1f}" font-size="{SIZE:.1f}" fill="{WARM}" '
            f'font-weight="700">{escape(key)}</text>'
            f'<text x="{PAD + KEY_W:.1f}" y="{y:.1f}" font-size="{SIZE:.1f}" '
            f'fill="{INK}">{escape(str(value))}</text>'
            f'{anim(n * step)}</g>'
        )
        y += LINE
        n += 1

    highlights = profile.get("highlights") or []
    if highlights:
        y += 6
        out.append(
            f'<g opacity="1"><text x="{PAD}" y="{y:.1f}" font-size="{SIZE:.1f}" '
            f'fill="{FAINT}">{"-" * 34}</text>{anim(n * step)}</g>'
        )
        y += LINE
        n += 1
        for item in highlights:
            out.append(
                f'<g opacity="1">'
                f'<text x="{PAD}" y="{y:.1f}" font-size="{SIZE:.1f}" fill="{ACCENT}">'
                f'&#9656;</text>'
                f'<text x="{PAD + 16:.1f}" y="{y:.1f}" font-size="{SIZE:.1f}" '
                f'fill="{DIM}">{escape(str(item))}</text>'
                f'{anim(n * step)}</g>'
            )
            y += LINE
            n += 1

    # neofetch signs off with a strip of terminal colours; this one uses the
    # contribution-graph scale so the two cards share a vocabulary.
    y += 8
    swatch = []
    for i, c in enumerate(LEVELS):
        swatch.append(f'<rect x="{PAD + i * 26:.1f}" y="{y - SIZE:.1f}" width="22" '
                      f'height="11" rx="2" fill="{c}"/>')
    out.append(f'<g opacity="1">{"".join(swatch)}{anim(n * step)}</g>')
    y += 12

    return out, y + PAD


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", type=Path, default=Path("profile.json"))
    ap.add_argument("-o", "--out", type=Path, default=Path("info-card.svg"))
    ap.add_argument("--width", type=int, default=520)
    args = ap.parse_args()

    profile = json.loads(args.profile.read_text())
    body, height = rows_svg(profile)
    w, h = args.width, int(height)

    label = f"{profile.get('name', 'profile')} - role, stack and highlights"
    svg = "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">',
        f'<style><![CDATA[text{{font-family:{MONO};white-space:pre}}]]></style>',
        f'<rect width="{w}" height="{h}" rx="10" fill="{PANEL}" '
        f'stroke="{BORDER}"/>',
        *body,
        "</svg>",
    ])
    args.out.write_text(svg)
    print(f"wrote {args.out} ({w}x{h})")


if __name__ == "__main__":
    main()
