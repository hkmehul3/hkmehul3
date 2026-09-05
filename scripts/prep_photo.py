#!/usr/bin/env python3
"""Prepare a source photo for ASCII conversion.

Honours EXIF orientation, crops to the subject, lifts the subject off the
background (so the background becomes empty space in the ASCII render),
then equalises contrast inside the subject only — a dark jacket and a
bright face both need to carry detail once the image is squeezed down to
~90 characters wide.

    python3 scripts/prep_photo.py assets/photo.jpg \
        --crop 0.27 0.355 0.73 0.72 -o assets/portrait.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def _fill_holes(m: np.ndarray) -> np.ndarray:
    """Fill enclosed background pockets, treating the bottom edge as inside.

    Without the bottom anchor, a notch that runs off the bottom of the frame
    (the gap between two halves of an open jacket) never closes and gets
    punched straight through the silhouette.
    """
    x = m.copy()
    x[-1, :] = 255
    pad = cv2.copyMakeBorder(x, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    cv2.floodFill(pad, np.zeros((x.shape[0] + 4, x.shape[1] + 4), np.uint8), (0, 0), 255)
    return cv2.bitwise_or(m, cv2.bitwise_not(pad)[1:-1, 1:-1])


def subject_mask(bgr: np.ndarray, gray: np.ndarray, *, inset: float, iters: int,
                 grow: int, dark: int, feather: float) -> np.ndarray:
    h, w = bgr.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    rect = (int(w * inset), int(h * 0.02), int(w * (1 - 2 * inset)), int(h * 0.97))
    cv2.grabCut(bgr, mask, rect, np.zeros((1, 65), np.float64),
                np.zeros((1, 65), np.float64), iters, cv2.GC_INIT_WITH_RECT)
    m = np.where((mask == 2) | (mask == 0), 0, 255).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    m = _fill_holes(m)

    # GrabCut shaves dark hair against a bright sky. Anything dark and close
    # to the silhouette is almost certainly still the subject.
    if grow > 0:
        near = cv2.dilate(m, np.ones((grow, grow), np.uint8))
        m = cv2.bitwise_or(m, cv2.bitwise_and(near, (gray < dark).astype(np.uint8) * 255))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        m = _fill_holes(m)

    n, lab, stats, _ = cv2.connectedComponentsWithStats((m > 128).astype(np.uint8), 8)
    if n > 1:
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        m = (lab == keep).astype(np.uint8) * 255

    if feather > 0:
        m = cv2.GaussianBlur(m, (0, 0), feather)
    return m


def find_face(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Locate the largest face, trying frontal then profile cascades."""
    side = max(64, int(min(gray.shape) * 0.18))
    for name in ("haarcascade_frontalface_alt2.xml",
                 "haarcascade_frontalface_default.xml",
                 "haarcascade_profileface.xml"):
        found = cv2.CascadeClassifier(cv2.data.haarcascades + name).detectMultiScale(
            gray, 1.05, 4, minSize=(side, side))
        if len(found):
            x, y, w, h = max(found, key=lambda r: r[2] * r[3])
            return int(x), int(y), int(w), int(h)
    return None


def face_weight(shape: tuple[int, int], box: tuple[int, int, int, int],
                grow: float) -> np.ndarray:
    """A soft 0..1 ellipse over the face, feathered so the boost has no seam."""
    h, w = shape
    x, y, bw, bh = box
    cx, cy = x + bw / 2, y + bh / 2
    rx, ry = bw * grow / 2, bh * grow / 2
    f = np.zeros((h, w), np.float32)
    cv2.ellipse(f, (int(cx), int(cy)), (int(rx), int(ry)), 0, 0, 360, 1.0, -1)
    return cv2.GaussianBlur(f, (0, 0), max(rx, ry) * 0.30)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("assets/portrait.png"))
    ap.add_argument("--crop", type=float, nargs=4, metavar=("L", "T", "R", "B"),
                    default=[0.0, 0.0, 1.0, 1.0])
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--no-cutout", action="store_true")
    ap.add_argument("--inset", type=float, default=0.05)
    ap.add_argument("--grabcut-iters", type=int, default=10)
    ap.add_argument("--grow", type=int, default=25)
    ap.add_argument("--dark", type=int, default=130)
    ap.add_argument("--feather", type=float, default=1.5)
    ap.add_argument("--clahe", type=float, default=2.0)
    ap.add_argument("--tiles", type=int, default=10)
    ap.add_argument("--lo", type=float, default=1.5, help="black point percentile")
    ap.add_argument("--hi", type=float, default=99.0, help="white point percentile")
    ap.add_argument("--focus", type=float, default=1.0,
                    help="0 disables the face focal boost")
    ap.add_argument("--focus-grow", type=float, default=1.5,
                    help="ellipse size relative to the detected face box")
    ap.add_argument("--focus-lift", type=float, default=12.0,
                    help="brightness added inside the face ellipse")
    args = ap.parse_args()

    im = ImageOps.exif_transpose(Image.open(args.src)).convert("RGB")
    w, h = im.size
    l, t, r, b = args.crop
    im = im.crop((int(l * w), int(t * h), int(r * w), int(b * h)))
    im = im.resize((args.width, max(1, int(args.width * im.height / im.width))),
                   Image.LANCZOS)

    bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    m = (np.full(gray.shape, 255, np.uint8) if args.no_cutout else
         subject_mask(bgr, gray, inset=args.inset, iters=args.grabcut_iters,
                      grow=args.grow, dark=args.dark, feather=args.feather))

    g = gray.astype(np.float32)
    inside = m > 200
    if inside.any():
        lo, hi = np.percentile(g[inside], [args.lo, args.hi])
        g = np.clip((g - lo) / max(1e-6, hi - lo), 0, 1) * 255.0

    if args.clahe > 0:
        eq = cv2.createCLAHE(clipLimit=args.clahe,
                             tileGridSize=(args.tiles, args.tiles)
                             ).apply(g.astype(np.uint8)).astype(np.float32)
        # Blend, so local contrast opens up the shadows without erasing the
        # overall light/dark structure of the photo.
        g = 0.55 * g + 0.45 * eq

    if args.focus > 0:
        box = find_face(gray)
        if box is None:
            print("  (no face found; skipping focal boost)")
        else:
            f = face_weight(gray.shape, box, args.focus_grow)
            sharp = cv2.addWeighted(g, 1.9, cv2.GaussianBlur(g, (0, 0), 3.0), -0.9, 0)
            boosted = np.clip((sharp - 128.0) * 1.25 + 128.0 + args.focus_lift, 0, 255)
            # Pull detail and light into the face; let everything else fall
            # back a little so the eye lands there first.
            g = g * (1 - f) * (1 - args.focus * 0.22) + boosted * f
            g = np.clip(g, 0, 255)

    a = m.astype(np.float32) / 255.0
    g = g * a  # background knocked to black -> empty space in the ASCII render

    out = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(args.out)
    print(f"wrote {args.out} {out.size}")


if __name__ == "__main__":
    main()
