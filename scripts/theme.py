"""Shared palette and SVG helpers for the generated profile art."""
from __future__ import annotations

BG = "#0d1117"
PANEL = "#0d1117"
BORDER = "#21262d"
INK = "#c9d1d9"
DIM = "#7d8590"
FAINT = "#484f58"
ACCENT = "#22d3ee"
WARM = "#f0883e"

# GitHub-style contribution scale, dark theme.
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

MONO = ('"SFMono-Regular",Consolas,"Liberation Mono",Menlo,'
        '"DejaVu Sans Mono",monospace')


def prompt_line(x: float, y: float, text: str, size: float,
                accent: str = ACCENT, ink: str = INK) -> str:
    """A `user@host ~ $ command` line, with the $ picked out in the accent."""
    from xml.sax.saxutils import escape
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.2f}" fill="{ink}">'
            f'<tspan fill="{accent}">$</tspan> {escape(text)}</text>')
