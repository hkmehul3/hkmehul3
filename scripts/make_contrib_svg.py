#!/usr/bin/env python3
"""Draw the contribution heatmap as an animated SVG.

Pulls the real calendar from GitHub's GraphQL API and reveals the grid
cell by cell in a diagonal sweep, then holds the finished graph. Run by
.github/workflows/update-profile-art.yml once a day.

    GITHUB_TOKEN=... python3 scripts/make_contrib_svg.py --user <login>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

import requests

from theme import ACCENT, BORDER, DIM, FAINT, INK, LEVELS, MONO, PANEL

API = "https://api.github.com/graphql"
QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""

CELL = 12.0
GAP = 3.0
PAD = 20.0
TOP = 46.0
LEFT = 34.0
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch(login: str, token: str) -> dict:
    to = datetime.utcnow().replace(microsecond=0)
    frm = to - timedelta(days=364)
    r = requests.post(
        API,
        json={"query": QUERY, "variables": {
            "login": login,
            "from": frm.isoformat() + "Z",
            "to": to.isoformat() + "Z",
        }},
        headers={"Authorization": f"bearer {token}",
                 "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()
    if payload.get("errors"):
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    user = payload["data"]["user"]
    if user is None:
        raise SystemExit(f"no such user: {login}")
    return user["contributionsCollection"]["contributionCalendar"]


def fetch_public(login: str) -> dict:
    """Read the calendar off the public profile, no token required.

    GitHub renders the graph server-side at /users/<login>/contributions, so
    the same numbers are available without authenticating. Only public
    activity is counted, which is exactly what the profile page shows anyway.
    """
    r = requests.get(
        f"https://github.com/users/{login}/contributions",
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            # GitHub serves 403 to obviously-scripted agents on this endpoint.
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36"),
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
    )
    if r.status_code == 404:
        raise SystemExit(f"no such user: {login}")
    r.raise_for_status()

    # Each day is an empty <td id="contribution-day-component-W-D" data-date=…>
    # and the count lives in a sibling <tool-tip for="<that id>">, so the two
    # have to be joined on the cell id.
    cells = re.findall(
        r'<td\b(?=[^>]*\bclass="[^"]*ContributionCalendar-day)'
        r'(?=[^>]*\bid="([^"]+)")(?=[^>]*\bdata-date="(\d{4}-\d{2}-\d{2})")',
        r.text)
    tips = dict(re.findall(r'<tool-tip\b[^>]*\bfor="([^"]+)"[^>]*>(.*?)</tool-tip>',
                           r.text, flags=re.S))
    if not cells:
        raise SystemExit("could not parse the public contribution calendar")

    by_date: dict[str, int] = {}
    for cell_id, iso in cells:
        m = re.search(r"(No|[\d,]+)\s+contribution", tips.get(cell_id, ""))
        by_date[iso] = 0 if (not m or m.group(1) == "No") else int(m.group(1).replace(",", ""))

    # Rebuild the Sunday-aligned week grid the renderer expects.
    days = sorted(by_date)
    start = date.fromisoformat(days[0])
    start -= timedelta(days=(start.weekday() + 1) % 7)
    end = date.fromisoformat(days[-1])

    weeks, week, d = [], [], start
    while d <= end:
        week.append({"date": d.isoformat(),
                     "contributionCount": by_date.get(d.isoformat(), 0),
                     "weekday": (d.weekday() + 1) % 7})
        if len(week) == 7:
            weeks.append({"contributionDays": week})
            week = []
        d += timedelta(days=1)
    if week:
        weeks.append({"contributionDays": week})

    return {"totalContributions": sum(by_date.values()), "weeks": weeks}


def level(count: int, peak: int) -> int:
    if count <= 0:
        return 0
    if peak <= 1:
        return 4
    # Quartiles of the non-zero range, so the scale adapts to how busy the
    # year actually was instead of assuming a fixed ceiling.
    for i, frac in enumerate((0.25, 0.50, 0.75), start=1):
        if count <= max(1, round(peak * frac)):
            return i
    return 4


def streaks(days: list[tuple[date, int]]) -> tuple[int, int]:
    best = cur = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        best = max(best, run)
    for _, c in reversed(days):
        # Today counts as neutral rather than as a broken streak: the day is
        # not over yet.
        if c > 0:
            cur += 1
        elif cur or len(days) == 0:
            break
        else:
            break
    return cur, best


def build(cal: dict, login: str, dur: float, hold: float) -> str:
    weeks = cal["weeks"]
    days: list[tuple[date, int]] = []
    for w in weeks:
        for d in w["contributionDays"]:
            days.append((date.fromisoformat(d["date"]), d["contributionCount"]))
    peak = max((c for _, c in days), default=0)

    cols = len(weeks)
    width = int(LEFT + cols * (CELL + GAP) + PAD)
    height = int(TOP + 7 * (CELL + GAP) + 46)
    cycle = dur + hold

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{escape(login)} - GitHub contributions, last year">',
        f'<style><![CDATA[text{{font-family:{MONO}}}]]></style>',
        f'<rect width="{width}" height="{height}" rx="10" fill="{PANEL}" '
        f'stroke="{BORDER}"/>',
    ]

    # Month ruler: label a week only when it is the first of a new month, and
    # only if there is room since the last label — the first column often
    # straddles a month boundary, which would collide two labels.
    seen = None
    last_x = -99.0
    for x, w in enumerate(weeks):
        d = date.fromisoformat(w["contributionDays"][0]["date"])
        px = LEFT + x * (CELL + GAP)
        if d.month != seen:
            seen = d.month
            if px - last_x < 26:
                continue
            last_x = px
            parts.append(
                f'<text x="{px:.1f}" y="{TOP - 10:.1f}" '
                f'font-size="10" fill="{DIM}">{MONTHS[d.month - 1]}</text>'
            )

    for i, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        parts.append(
            f'<text x="{PAD - 12:.1f}" y="{TOP + i * (CELL + GAP) + CELL - 2:.1f}" '
            f'font-size="9" fill="{FAINT}">{name}</text>'
        )

    for x, w in enumerate(weeks):
        for d in w["contributionDays"]:
            y = d["weekday"]
            c = d["contributionCount"]
            fill = LEVELS[level(c, peak)]
            # Diagonal sweep: later columns and lower rows start later.
            begin = (x / max(1, cols - 1)) * dur * 0.92 + y * (dur * 0.012)
            px = LEFT + x * (CELL + GAP)
            py = TOP + y * (CELL + GAP)
            parts.append(
                f'<rect x="{px:.1f}" y="{py:.1f}" width="{CELL}" height="{CELL}" '
                f'rx="2.5" fill="{fill}" opacity="1">'
                f'<title>{d["date"]}: {c} contribution{"" if c == 1 else "s"}</title>'
                f'<animate attributeName="opacity" values="0;0;1;1" '
                f'keyTimes="0;{begin / cycle:.5f};'
                f'{min(0.9999, (begin + 0.45) / cycle):.5f};1" dur="{cycle:.2f}s" '
                f'repeatCount="indefinite"/>'
                f'</rect>'
            )

    cur, best = streaks(days)
    total = cal["totalContributions"]
    fy = TOP + 7 * (CELL + GAP) + 26
    parts.append(
        f'<text x="{LEFT:.1f}" y="{fy:.1f}" font-size="11.5" fill="{INK}">'
        f'<tspan fill="{ACCENT}">{total:,}</tspan> contributions in the last year'
        f'<tspan fill="{FAINT}">   |   </tspan>'
        f'<tspan fill="{ACCENT}">{cur}</tspan> day current streak'
        f'<tspan fill="{FAINT}">   |   </tspan>'
        f'<tspan fill="{ACCENT}">{best}</tspan> day best'
        f'</text>'
    )

    legend_x = width - PAD - 5 * (CELL + 2) - 46
    parts.append(f'<text x="{legend_x - 26:.1f}" y="{fy:.1f}" font-size="10" '
                 f'fill="{FAINT}">less</text>')
    for i, c in enumerate(LEVELS):
        parts.append(f'<rect x="{legend_x + i * (CELL + 2):.1f}" y="{fy - 9:.1f}" '
                     f'width="{CELL}" height="{CELL}" rx="2.5" fill="{c}"/>')
    parts.append(f'<text x="{legend_x + 5 * (CELL + 2) + 4:.1f}" y="{fy:.1f}" '
                 f'font-size="10" fill="{FAINT}">more</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user")
    ap.add_argument("--profile", type=Path, default=Path("profile.json"))
    ap.add_argument("-o", "--out", type=Path, default=Path("contrib-graph.svg"))
    ap.add_argument("--dur", type=float, default=3.4, help="sweep length, seconds")
    ap.add_argument("--hold", type=float, default=11.0, help="pause before looping")
    ap.add_argument("--cache", type=Path, help="write/read the raw calendar JSON")
    ap.add_argument("--public", action="store_true",
                    help="ignore any token and scrape the public calendar")
    args = ap.parse_args()

    login = args.user
    if not login and args.profile.exists():
        login = json.loads(args.profile.read_text()).get("username")
    if not login:
        raise SystemExit("need --user or a username in profile.json")

    token = None if args.public else (os.environ.get("GH_PAT")
                                      or os.environ.get("GITHUB_TOKEN"))
    try:
        # A token also surfaces private contributions; without one the public
        # profile page carries the same numbers the profile itself shows.
        cal = fetch(login, token) if token else fetch_public(login)
    except Exception as exc:
        if not (args.cache and args.cache.exists()):
            raise
        print(f"live fetch failed ({exc}); using the cached calendar", file=sys.stderr)
        cal = json.loads(args.cache.read_text())
    else:
        if args.cache:
            args.cache.write_text(json.dumps(cal))

    args.out.write_text(build(cal, login, args.dur, args.hold))
    print(f"wrote {args.out} ({cal['totalContributions']} contributions)")


if __name__ == "__main__":
    main()
