#!/usr/bin/env python3
"""The desktop's loading screen after sign-in (KSplash): "Sloth OS" sprayed on like graffiti, then the letters turn
into the logo (developer tool, not in the image).

The letters are sprayed from left to right (a mist around the can, a few drips), then they break into points of
light that fly into the logo's shape, as in TV mode's start-up video (tools/make_tv_intro.py). The last frame is the
logo exactly where Splash.qml shows it, so Splash.qml switches to the still logo (and makes it pulse until the
desktop is ready) without a jump. About 2.6 seconds; an animated WebP that plays once (Qt's WebP plugin plays it).

The letters: Rubik Spray Paint (SIL Open Font License 1.1, Google Fonts:
https://github.com/google/fonts/raw/main/ofl/rubikspraypaint/RubikSprayPaint-Regular.ttf). Only the rendered
picture goes into the image, not the font.

Needs: python3-numpy, python3-pillow.
Usage: python3 tools/make_splash_intro.py RubikSprayPaint-Regular.ttf [folder for a few still frames]
       (writes files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/contents/splash/images/intro.webp)
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_tv_intro import BG, phase, sample  # noqa: E402  (the same background and particle helpers)

REPO = Path(__file__).resolve().parent.parent
SPLASH = REPO / "files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/contents/splash/images"
OUT = SPLASH / "intro.webp"
LOGO = SPLASH / "logo.png"             # the very logo Splash.qml shows after the intro, so they match exactly

CW, CH, FPS = 1200, 720, 30            # the picture; Splash.qml scales it so the logo is root.logoSize tall
LOGO_PX = 480                          # the logo's size in the picture (Splash.qml: images/logo.png, 480)
N = 7000
SEED = 11
PAINT = np.array([232, 234, 238], float)

SPRAY = (0.05, 1.30)                   # the letters are sprayed on
DRIP = (0.6, 1.6)                      # drips run down
BREAK = (1.45, 1.75)                   # the letters turn into points
FLY = (1.55, 2.35)                     # the points fly into the logo
FORM = (2.25, 2.6)                     # the logo appears
END = 2.6


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    font_path = sys.argv[1]
    shots = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    rng = np.random.default_rng(SEED)
    logo = Image.open(LOGO).convert("RGBA")
    assert logo.size == (LOGO_PX, LOGO_PX)
    lx, ly = (CW - LOGO_PX) // 2, (CH - LOGO_PX) // 2

    # the letters, as a mask as wide as most of the picture
    font = ImageFont.truetype(font_path, 200)
    box = font.getbbox("Sloth OS")
    text = Image.new("L", (CW, CH), 0)
    tw, th = box[2] - box[0], box[3] - box[1]
    tx, ty = (CW - tw) // 2 - box[0], (CH - th) // 2 - box[1]
    ImageDraw.Draw(text).text((tx, ty), "Sloth OS", font=font, fill=255)
    tarr = np.asarray(text, float) / 255
    left, right = (CW - tw) // 2, (CW + tw) // 2
    top, bottom = (CH - th) // 2, (CH + th) // 2
    ramp = np.linspace(1.0, 0.82, CH)[:, None, None]            # a little darker towards the bottom
    paint_rgb = PAINT * ramp

    # the edge of the paint is ragged: each row reaches the can a little earlier or later
    jitter = rng.normal(0, 14, CH).cumsum()
    jitter = (jitter - jitter.mean()) * 0.15
    jitter = np.clip(jitter, -30, 30)[:, None]
    xs = np.arange(CW)[None, :]

    # drips: under a few letters' lower edge
    cols = np.nonzero(tarr[bottom - 12:bottom].max(axis=0) > 0.5)[0]
    drips = []
    for x in rng.permutation(cols):
        if len(drips) == 5:
            break
        if any(abs(int(x) - d[0]) < 110 for d in drips):  # apart from each other
            continue
        y0 = bottom - 12 + int(np.nonzero(tarr[bottom - 12:bottom, x] > 0.5)[0].max())
        drips.append((int(x), y0, rng.uniform(22, 55), rng.uniform(6, 9)))

    texture = 0.9 + 0.1 * np.asarray(Image.fromarray((rng.random((CH, CW)) * 255).astype(np.uint8))
                                      .filter(ImageFilter.GaussianBlur(1.2)), float) / 255
    mist = np.zeros((CH, CW), float)                              # overspray: stays faintly
    src = sample(text, N, rng)
    dst = sample(logo.getchannel("A"), N, rng)
    src = src[np.lexsort((src[:, 0], src[:, 1]))]
    dst = dst[np.lexsort((dst[:, 0], dst[:, 1]))]
    larr = np.asarray(logo, float)
    col_dst = larr[dst[:, 1].astype(int), dst[:, 0].astype(int), :3]
    dst += (lx, ly)
    delay = rng.random(N) * 0.3
    swirl = (rng.random(N) - 0.5) * 2
    bright = 0.8 + rng.random(N) * 0.4

    frames = []
    total = int(round(END * FPS))
    for f in range(total + 1):
        t = f / FPS
        out = np.empty((CH, CW, 3), float)
        out[:] = BG
        p = phase(t, SPRAY)
        a_text = 1 - phase(t, BREAK)
        if a_text > 0 and p > 0:
            can_x = left - 40 + p * (tw + 80)
            can_y = (top + bottom) / 2 + math.sin(t * 38) * th * 0.42  # the can goes up and down as it moves
            reveal = np.clip((can_x - xs + jitter) / 36, 0, 1)
            if p < 1:                                             # the mist around the can, this frame
                n = 2200
                r = np.abs(rng.normal(0, 60, n))
                ang = rng.random(n) * 2 * math.pi
                mx = np.clip((can_x + r * np.cos(ang)).astype(int), 0, CW - 1)
                my = np.clip((can_y + r * np.sin(ang)).astype(int), 0, CH - 1)
                np.add.at(mist, (my, mx), 0.09)
            cover = tarr * reveal
            for x, y0, length, width in drips:                   # drips grow below the letters
                k = phase(t, DRIP) * min(1.0, max(0.0, (can_x - x) / 120))
                if k <= 0:
                    continue
                y1 = int(y0 + length * k)
                for y in range(y0, y1):                           # narrower lower down
                    half = width / 2 * (1 - 0.35 * (y - y0) / max(1, length))
                    x0, x1 = int(x - half), int(x + half + 1)
                    cover[y, x0:x1] = np.maximum(cover[y, x0:x1], 0.95)
                yy, xx = np.ogrid[:CH, :CW]
                blob = ((xx - x) ** 2 + (yy - y1) ** 2) <= (width * 0.6) ** 2
                cover[blob] = np.maximum(cover[blob], 0.95)
            cover = cover * texture                               # the paint is not perfectly even
            m = np.clip(mist, 0, 0.4)
            paint = np.clip(cover + m * (1 - cover), 0, 1) * a_text
            out = out * (1 - paint[..., None]) + paint_rgb * paint[..., None]
        a_dots = phase(t, BREAK) * (1 - phase(t, FORM))
        if a_dots > 0:
            k = np.clip((t - FLY[0]) / (FLY[1] - FLY[0]) * 1.3 - delay, 0, 1)
            k = k * k * (3 - 2 * k)
            pos = src * (1 - k[:, None]) + dst * k[:, None]
            arc = np.sin(k * math.pi)
            pos[:, 0] += swirl * arc * 90
            pos[:, 1] -= arc * 60 * (0.4 + 0.6 * np.abs(swirl))
            col = (PAINT * (1 - k[:, None]) + col_dst * k[:, None]) * bright[:, None]
            col = np.clip(col * (1 + 0.5 * arc[:, None]), 0, 255)
            acc = np.zeros((CH, CW, 3), float)
            xi = np.clip(pos[:, 0].astype(int), 0, CW - 2)
            yi = np.clip(pos[:, 1].astype(int), 0, CH - 2)
            for ox in (0, 1):
                for oy in (0, 1):
                    np.maximum.at(acc, (yi + oy, xi + ox), col)
            glow = np.asarray(Image.fromarray(acc.astype(np.uint8)).filter(ImageFilter.GaussianBlur(5)), float)
            out = out + (acc + glow * 0.9) * a_dots
        img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
        a_logo = phase(t, FORM) if f < total else 1.0
        if a_logo > 0:
            lay = logo.copy()
            lay.putalpha(lay.getchannel("A").point(lambda v, k=a_logo: int(v * k)))
            img.paste(lay, (lx, ly), lay)
        frames.append(img)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=round(1000 / FPS), loop=1,
                   quality=82, method=6)
    if shots:
        for name, f in (("spray", 20), ("sprayed", 42), ("flight", 58), ("logo", total)):
            frames[f].save(shots / f"splash-{name}.png")
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
