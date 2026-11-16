#!/usr/bin/env python3
"""The desktop's loading screen after sign-in (KSplash): "Sloth OS" written on the wall like a tag, in silver spray
paint, then the logo comes forward (developer tool, not in the image).

The logo waits faint and a little bigger in the background. The tag is written stroke by stroke, as a hand with a
spray can would: the paint follows the letters' strokes (their skeleton, in order), with a mist around the nozzle and
a few drips running down. Then the tag fades away and the logo comes forward: it shrinks a little to its place and
gets its full brightness, exactly where Splash.qml shows the still logo, so Splash.qml switches to it (and makes it
pulse until the desktop is ready) without a jump. About 3.3 seconds; an animated WebP that plays once (Qt's WebP
plugin plays it).

The picture is 1920 x 1080 with the logo LOGO_PX tall in its middle: Splash.qml scales it so the logo is as tall as
its still logo (on a 1080p screen 1:1, the whole screen).

The letters: Sedgwick Ave Display (SIL Open Font License 1.1, Google Fonts:
https://github.com/google/fonts/raw/main/ofl/sedgwickavedisplay/SedgwickAveDisplay-Regular.ttf). Only the rendered
picture goes into the image, not the font.

Needs: python3-numpy, python3-pillow, python3-scipy, python3-scikit-image (ffmpeg for the preview video).
Usage: python3 tools/make_splash_intro.py SedgwickAveDisplay-Regular.ttf [folder for still frames and a preview]
       (writes files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/contents/splash/images/intro.webp)
"""
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from skimage.morphology import skeletonize

REPO = Path(__file__).resolve().parent.parent
SPLASH = REPO / "files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/contents/splash/images"
OUT = SPLASH / "intro.webp"
LOGO = SPLASH / "logo.png"             # the very logo Splash.qml shows after the intro, so they match exactly

CW, CH, FPS = 1920, 1080, 30
LOGO_PX = 346                          # the logo's size in the picture: Splash.qml's logoSize on a 1080p screen
BG = np.array([28, 30, 33], float)     # #1c1e21, Splash.qml's background
TEXT = "Sloth OS"
FONT_PX = 400
TILT = 4                               # degrees: a tag goes up a little to the right
SEED = 3
# silver, as the logo: lighter at the top, darker at the bottom
SILVER_TOP, SILVER_BOTTOM = np.array([236, 239, 243], float), np.array([150, 156, 164], float)

# timeline (seconds)
LOGO_IN = (0.0, 0.4)                   # the faint logo appears in the background
GHOST, GHOST_SCALE = 0.13, 1.45        # ...this bright and this much bigger
WRITE = (0.15, 1.95)                   # the tag is written
DRIP = (0.9, 2.3)                      # drips run down
FADE = (2.25, 2.8)                     # the tag fades away
FORWARD = (2.35, 3.15)                 # the logo comes forward: shrinks to its place, full brightness
END = 3.3


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def phase(t, span, f=ease):
    return f((t - span[0]) / (span[1] - span[0]))


def stroke_order(skel):
    """The skeleton's pixels in the order a hand would paint them: shape by shape from left to right, each traced
    from its leftmost end along its lines (a depth-first walk; at a fork one branch, then back for the other).
    -> (array of (y, x), order map: index of each skeleton pixel, -1 elsewhere)"""
    h, w = skel.shape
    labels, n = ndimage.label(skel, structure=np.ones((3, 3)))
    comps = sorted(range(1, n + 1), key=lambda c: np.nonzero(labels == c)[1].min())
    nb = ndimage.convolve(skel.astype(int), np.ones((3, 3), int), mode="constant") - 1
    order = np.full((h, w), -1, int)
    path = []
    steps = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for c in comps:
        ys, xs = np.nonzero(labels == c)
        ends = [(y, x) for y, x in zip(ys, xs) if nb[y, x] == 1]
        start = min(ends or list(zip(ys, xs)), key=lambda p: (p[1], p[0]))
        stack = [start]
        while stack:
            y, x = stack.pop()
            if order[y, x] >= 0:
                continue
            order[y, x] = len(path)
            path.append((y, x))
            nxt = [(y + dy, x + dx) for dy, dx in steps
                   if 0 <= y + dy < h and 0 <= x + dx < w and skel[y + dy, x + dx] and order[y + dy, x + dx] < 0]
            # straight neighbours last on the stack (painted first), so the line goes on rather than jumping
            nxt.sort(key=lambda p: abs(p[0] - y) + abs(p[1] - x), reverse=True)
            stack.extend(nxt)
    return np.array(path), order


def logo_layer(canvas, logo_full, size, alpha):
    """The logo, `size` pixels tall, in the middle of the canvas."""
    lg = np.asarray(logo_full.resize((size, size), Image.LANCZOS), float)
    x0, y0 = (CW - size) // 2, (CH - size) // 2
    la = lg[..., 3:4] / 255 * alpha
    canvas[y0:y0 + size, x0:x0 + size] = canvas[y0:y0 + size, x0:x0 + size] * (1 - la) + lg[..., :3] * la


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    font = ImageFont.truetype(sys.argv[1], FONT_PX)
    shots = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    rng = np.random.default_rng(SEED)

    # the tag: one line, centred, turned up a little
    box = font.getbbox(TEXT)
    tw, th = box[2] - box[0], box[3] - box[1]
    img = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(img).text(((CW - tw) / 2 - box[0], (CH - th) / 2 - box[1] - 20), TEXT, font=font, fill=255)
    img = img.rotate(TILT, resample=Image.BICUBIC, center=(CW / 2, CH / 2))
    mask = np.asarray(img, float) / 255 > 0.5
    ys, xs = np.nonzero(mask)
    top, bottom, left, right = ys.min(), ys.max(), xs.min(), xs.max()

    # the order of painting: every pixel of the letters belongs to its nearest skeleton pixel
    skel = skeletonize(mask)
    path, order = stroke_order(skel)
    _, (iy, ix) = ndimage.distance_transform_edt(~skel, return_indices=True)
    pixel_order = np.where(mask, order[iy, ix], -1).astype(float)
    n_path = len(path)
    stroke_w = 2 * ndimage.distance_transform_edt(mask)[skel].mean()

    # drips: from a few of the lowest points of the letters
    drips = []
    low_cols = [x for x in range(left, right) if mask[:, x].any() and np.nonzero(mask[:, x])[0].max() > bottom - 60]
    for x in rng.permutation(low_cols):
        if len(drips) == 4:
            break
        if any(abs(int(x) - d[0]) < 160 for d in drips):
            continue
        y0 = int(np.nonzero(mask[:, x])[0].max())
        drips.append((int(x), y0, rng.uniform(45, 100), rng.uniform(9, 13), order[iy[y0, x], ix[y0, x]]))

    # the paint's colour by height, and its slightly uneven spray texture
    ramp = np.clip((np.arange(CH) - top) / max(1, bottom - top), 0, 1)
    silver = SILVER_TOP[None, :] * (1 - ramp[:, None]) + SILVER_BOTTOM[None, :] * ramp[:, None]
    texture = np.clip(0.88 + 0.24 * (ndimage.gaussian_filter(rng.random((CH, CW)), 1.1) - 0.5) * 4, 0.75, 1.0)
    edge = ndimage.gaussian_filter(mask.astype(float), 1.4)        # a sprayed edge is soft
    mist = np.zeros((CH, CW))
    logo_full = Image.open(LOGO).convert("RGBA")

    frames = []
    n = int(round(END * FPS))
    for f in range(n + 1):
        t = f / FPS
        canvas = np.empty((CH, CW, 3))
        canvas[:] = BG

        # the logo: faint and bigger in the background, then forward to its place
        fw = phase(t, FORWARD, ease_out)
        scale = GHOST_SCALE + (1 - GHOST_SCALE) * fw
        alpha = GHOST * phase(t, LOGO_IN) * (1 - fw) + fw
        if f == n:
            logo_layer(canvas, logo_full, LOGO_PX, 1.0)
            frames.append(Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB"))
            break
        if alpha > 0:
            logo_layer(canvas, logo_full, int(round(LOGO_PX * scale)), alpha)

        # the tag, painted up to where the nozzle is now
        w = min(max((t - WRITE[0]) / (WRITE[1] - WRITE[0]), 0.0), 1.0)   # a steady hand
        done = w * (n_path + 40)
        if 0 < w < 1 and done < n_path:                             # the mist around the nozzle
            ny, nx = path[int(done)]
            k = 900
            r = np.abs(rng.normal(0, stroke_w * 0.9, k))
            ang = rng.random(k) * 2 * math.pi
            my = np.clip((ny + r * np.sin(ang)).astype(int), 0, CH - 1)
            mx = np.clip((nx + r * np.cos(ang)).astype(int), 0, CW - 1)
            np.add.at(mist, (my, mx), 0.06)
        cover = np.clip((done - pixel_order) / 18, 0, 1) * (pixel_order >= 0)
        cover = ndimage.gaussian_filter(cover, 1.0) * edge
        dr = phase(t, DRIP)
        for x, y0, length, width, at in drips:                     # a drip starts once its place is painted
            if done < at or dr <= 0:
                continue
            y1 = min(CH - 12, int(y0 + length * dr))
            for y in range(y0 - 3, y1):
                half = width / 2 * (1 - 0.35 * (y - y0) / length)
                cover[y, int(x - half):int(x + half + 1)] = np.maximum(cover[y, int(x - half):int(x + half + 1)], 0.9)
            yy, xx = np.ogrid[y1 - 10:y1 + 11, x - 10:x + 11]
            blob = (xx - x) ** 2 + (yy - y1) ** 2 <= (width * 0.65) ** 2
            cover[y1 - 10:y1 + 11, x - 10:x + 11] = np.maximum(cover[y1 - 10:y1 + 11, x - 10:x + 11], blob * 0.9)
        speck = np.clip(ndimage.gaussian_filter(mist, 0.7), 0, 0.35)
        paint = np.clip(cover * texture + speck * (1 - cover), 0, 1)
        paint *= 1 - phase(t, FADE)
        canvas = canvas * (1 - paint[..., None]) + silver[:, None, :] * paint[..., None]
        frames.append(Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB"))
        print(f"\r{f + 1}/{n + 1}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=round(1000 / FPS), loop=1,
                   quality=80, method=6)
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB, {len(frames)} frames)")
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
        for old in shots.glob("splash-*"):
            old.unlink()
        for name, sec in (("writing", 0.9), ("written", 2.1), ("fading", 2.55), ("forward", 2.8), ("logo", END)):
            frames[min(len(frames) - 1, int(sec * FPS))].save(shots / f"splash-{name}.png")
        if shutil.which("ffmpeg"):   # a preview to watch: the intro, then 3 s of Splash.qml's pulse
            tmp = shots / "frames"
            tmp.mkdir(exist_ok=True)
            pulse = []
            for k in range(3 * FPS):     # Splash.qml: 1.0 -> 1.06 -> 1.0 and opacity 1 -> 0.78 -> 1 in 1.6 s
                p = (1 - math.cos(2 * math.pi * k / (1.6 * FPS))) / 2
                c = np.empty((CH, CW, 3))
                c[:] = BG
                logo_layer(c, logo_full, int(round(LOGO_PX * (1 + 0.06 * p))), 1 - 0.22 * p)
                pulse.append(Image.fromarray(np.clip(c, 0, 255).astype(np.uint8), "RGB"))
            for k, fr in enumerate(frames + pulse):
                fr.save(tmp / f"{k:04d}.png")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(tmp / "%04d.png"),
                            "-c:v", "libvpx-vp9", "-b:v", "6M", "-pix_fmt", "yuv420p", str(shots / "splash-preview.webm")],
                           check=True)
            shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
