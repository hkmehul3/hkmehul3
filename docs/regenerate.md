# Regenerating the profile art

Everything on the profile is generated from `profile.json` plus the photo in
`assets/`. Edit the JSON, run the build, commit.

```bash
pip install -r requirements-dev.txt      # first time only
python3 scripts/build.py                 # rebuild everything
python3 scripts/build.py --skip-photo    # leave the ASCII portrait alone
```

## What each script does

| script | output | notes |
| --- | --- | --- |
| `prep_photo.py` | `assets/portrait.png` | crops the photo, cuts the subject out of the background with GrabCut, evens out contrast inside the silhouette, sharpens the detected face |
| `make_ascii_svg.py` | `ascii-portrait.svg` | samples that image into a character grid and writes an SVG that types itself in |
| `make_info_card.py` | `info-card.svg` | the neofetch-style panel, straight from `profile.json` |
| `make_contrib_svg.py` | `contrib-graph.svg` | the contribution heatmap |
| `make_readme.py` | `README.md` | assembles the page |

## Tuning the portrait

The `portrait` block in `profile.json` holds the settings the build uses:

- `crop` — `[left, top, right, bottom]` as fractions of the photo. Tighter
  framing means more characters land on the face.
- `cols` — characters across. More detail, smaller glyphs.
- `gamma` — below 1 brightens the midtones, above 1 darkens them.
- `floor` — brightness below this renders as blank space.

To try settings without touching the committed files:

```bash
python3 scripts/prep_photo.py assets/photo.jpg --crop 0.27 0.35 0.73 0.68 -o /tmp/p.png
python3 scripts/make_ascii_svg.py /tmp/p.png --cols 88 --aspect 0.575 \
    --char-w 4.6 --line-h 8.0 --gamma 0.8 --floor 0.04 --ceil 1.0 \
    -o /tmp/a.svg --txt /tmp/a.txt
python3 scripts/preview_ascii.py /tmp/a.txt /tmp/a.png 11   # look at /tmp/a.png
```

Swapping in a new photo: replace `assets/photo.jpg` and re-run the build. A
straight-on shot against a plain background, lit from one side, converts far
better than a three-quarter view in flat light.

## The contribution graph

`make_contrib_svg.py` reads the real calendar. With `GH_PAT` or `GITHUB_TOKEN`
set it uses the GraphQL API, which also counts private contributions; without
one it falls back to scraping the public profile page, which is what the
profile itself displays. `--public` forces the token-free path. The last good
calendar is cached in `assets/contrib-cache.json` and used if a fetch fails, so
a GitHub outage can never blank the graph.

`.github/workflows/update-profile-art.yml` reruns the graph daily at 03:20 UTC
and commits only when something actually changed. Add a `GH_PAT` repository
secret if you want private contributions counted.

## If the animations do not play

Every animated element is written so its *final* state is the default and the
animation runs from there. Anywhere SMIL is unavailable, the art still shows
up fully drawn rather than blank.
