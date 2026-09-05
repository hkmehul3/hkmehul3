#!/usr/bin/env python3
"""Generate README.md from profile.json.

Keeping the README generated means profile.json is the single place to edit
a link, a job title or a highlight.

    python3 scripts/make_readme.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote


def badge(link: dict) -> str:
    label = quote(str(link["label"]).replace("-", "--").replace("_", "__"))
    value = quote(str(link["value"]).replace("-", "--").replace("_", "__"))
    color = link.get("color", "0d1117")
    logo = link.get("logo", "github")
    logo_color = link.get("logoColor", "white")
    src = (f"https://img.shields.io/badge/{label}-{value}-{color}"
           f"?style=for-the-badge&logo={logo}&logoColor={logo_color}")
    return f'[![{link["label"]}]({src})]({link["url"]})'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", type=Path, default=Path("profile.json"))
    ap.add_argument("-o", "--out", type=Path, default=Path("README.md"))
    ap.add_argument("--body", type=Path, default=Path("sections/body.md"),
                    help="hand-written markdown appended below the header")
    args = ap.parse_args()

    p = json.loads(args.profile.read_text())
    user = p["username"]
    prompt = p.get("prompt", f"{user.lower()}@github")
    badges = "\n".join(badge(l) for l in p.get("links", []))

    md = f"""<div align="center">

<!-- Everything below is generated. Edit profile.json, then run:
       python3 scripts/build.py
     The contribution graph is also refreshed daily by
     .github/workflows/update-profile-art.yml -->

<h3><code>{prompt} ~ $ whoami</code></h3>

<table>
<tr>
<td valign="top"><img src="./ascii-portrait.svg" width="370" alt="{p['name']} — ASCII portrait" /></td>
<td valign="top"><img src="./info-card.svg" width="490" alt="{p['name']} — role, stack and highlights" /></td>
</tr>
</table>

<br>

<h3><code>{prompt} ~ $ ./contributions.sh</code></h3>

<img src="./contrib-graph.svg" width="860" alt="{p['name']}'s GitHub contribution graph — refreshed daily" />

<br>
<br>

<h3><code>{prompt} ~ $ ./links.sh</code></h3>

<p><b>{p['tagline']}</b></p>

{badges}

<br>

</div>
"""
    # Everything below the generated header is hand-written and simply passed
    # through, so editing prose never means editing this script.
    if args.body and args.body.exists():
        body = args.body.read_text().strip()
        if body:
            md += f"\n---\n\n{body}\n"

    args.out.write_text(md)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
