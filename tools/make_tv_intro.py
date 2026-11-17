#!/usr/bin/env python3
"""TV mode's start-up video: the Sloth OS logo turns into a game controller (developer tool, not in the image).

Steam (started as on SteamOS, /usr/libexec/sloth-os/tv-session) plays a video while it loads; by default that is
Valve's SteamOS logo. Steam plays a video from its config/uioverrides/movies/ folder when it is picked in its settings
(Customization → Startup Movie); /usr/libexec/sloth-os/tv-startup-movie puts this one there and picks it.

The logo breaks into points of light, they fly into the shape of a controller, and the controller appears in the
logo's silver, on the boot animation's background (files/system/usr/share/plymouth/themes/sloth-os). 6 seconds
(Steam plays at most about 10).

Needs: python3-numpy, python3-pillow, rsvg-convert (librsvg2-tools), ffmpeg with libvpx and libvorbis (ffmpeg-free).
Usage: python3 tools/make_tv_intro.py [folder for a few still frames]
       (writes files/system/usr/share/sloth-os/tv/startup.webm)
"""
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
LOGO = REPO / "files/system/usr/share/sloth-os/logo/sloth-logo.svg"
OUT = REPO / "files/system/usr/share/sloth-os/tv/startup.webm"

W, H, FPS = 1920, 1080, 30
BG = (28, 30, 33)                      # the boot animation's background (0.11, 0.118, 0.129)
SIZE = 560                             # the logo's and the controller's height on screen
N = 9000                               # points of light
SEED = 7

# Timeline (seconds)
LOGO_IN = (0.0, 1.0)                   # the logo fades in
HOLD_LOGO = 1.6                        # ...and stays until then
BREAK = (1.6, 2.1)                     # the logo turns into points
FLY = (2.0, 4.0)                       # the points fly into the controller's shape
FORM = (3.8, 4.4)                      # the controller appears in place of the points
END = 6.0
FADE_OUT = (5.5, 6.0)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def phase(t, span):
    a, b = span
    return ease((t - a) / (b - a))


def silver(mask):
    """A mask (L) filled with the logo's matt silver: lighter at the top, darker at the bottom."""
    h = mask.size[1]
    top, bottom = np.array([226, 229, 233], float), np.array([150, 156, 164], float)
    ramp = np.linspace(0, 1, h)[:, None, None]
    rgb = (top * (1 - ramp) + bottom * ramp).repeat(mask.size[0], axis=1).astype(np.uint8)
    img = Image.fromarray(rgb, "RGB").convert("RGBA")
    img.putalpha(mask)
    return img


def controller_mask(size):
    """A game controller's silhouette, drawn large and scaled down (smooth edges); holes for the buttons."""
    s = 4
    w, h = int(size * 1.62) * s, size * s
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    u = h / 100                        # one unit: a hundredth of the height
    cx = w / 2
    # the body: a wide rounded top part and two grips that go down and outwards
    d.rounded_rectangle([cx - 66 * u, 14 * u, cx + 66 * u, 66 * u], radius=24 * u, fill=255)
    for side in (-1, 1):
        gx = cx + side * 48 * u
        grip = Image.new("L", (w, h), 0)
        gd = ImageDraw.Draw(grip)
        gd.ellipse([gx - 22 * u, 30 * u, gx + 22 * u, 96 * u], fill=255)
        grip = grip.rotate(side * 18, center=(gx, 40 * u), resample=Image.BICUBIC)
        m.paste(255, mask=grip)
    # the shoulder buttons
    for side in (-1, 1):
        d.rounded_rectangle([cx + side * 52 * u - 15 * u, 6 * u, cx + side * 52 * u + 15 * u, 18 * u],
                            radius=6 * u, fill=255)
    # rounded joins where the parts meet (a light blur, then a sharp edge again); the holes come after, crisp
    m = m.filter(ImageFilter.GaussianBlur(1.5 * u)).point(lambda v: 255 if v > 128 else 0)
    d = ImageDraw.Draw(m)
    # holes: the cross on the left, four buttons on the right, two sticks, two small middle buttons
    dx, dy = cx - 44 * u, 36 * u
    d.rectangle([dx - 4 * u, dy - 12 * u, dx + 4 * u, dy + 12 * u], fill=0)
    d.rectangle([dx - 12 * u, dy - 4 * u, dx + 12 * u, dy + 4 * u], fill=0)
    bx, by = cx + 44 * u, 36 * u
    for ox, oy in ((0, -10), (10, 0), (0, 10), (-10, 0)):
        d.ellipse([bx + ox * u - 5 * u, by + oy * u - 5 * u, bx + ox * u + 5 * u, by + oy * u + 5 * u], fill=0)
    for sx in (-20, 20):
        x, y = cx + sx * u, 50 * u
        d.ellipse([x - 10 * u, y - 10 * u, x + 10 * u, y + 10 * u], fill=0)
        d.ellipse([x - 6 * u, y - 6 * u, x + 6 * u, y + 6 * u], fill=255)
    for sx in (-9, 9):
        d.ellipse([cx + sx * u - 3 * u, 30 * u - 3 * u, cx + sx * u + 3 * u, 30 * u + 3 * u], fill=0)
    return m.resize((w // s, h // s), Image.LANCZOS)


def sample(mask, n, rng):
    """n points inside a mask (weighted by its alpha), as float (x, y) in the mask's pixels."""
    a = np.asarray(mask, float)
    ys, xs = np.nonzero(a > 100)
    idx = rng.choice(len(xs), n, replace=len(xs) < n)
    return np.stack([xs[idx] + rng.random(n), ys[idx] + rng.random(n)], axis=1)


def main():
    for tool in ("rsvg-convert", "ffmpeg"):
        if not shutil.which(tool):
            sys.exit(f"{tool} is missing")
    rng = np.random.default_rng(SEED)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        subprocess.run(["rsvg-convert", "-w", str(SIZE), "-h", str(SIZE), "-o", tmp / "logo.png", LOGO], check=True)
        logo = Image.open(tmp / "logo.png").convert("RGBA")
        pad = silver(controller_mask(SIZE))

        lx, ly = (W - logo.width) // 2, (H - logo.height) // 2
        px, py = (W - pad.width) // 2, (H - pad.height) // 2
        src = sample(logo.getchannel("A"), N, rng)
        dst = sample(pad.getchannel("A"), N, rng)
        # rows go to rows (sorted top to bottom), so the logo flows into the controller instead of scattering
        src = src[np.lexsort((src[:, 0], src[:, 1]))]
        dst = dst[np.lexsort((dst[:, 0], dst[:, 1]))]
        larr = np.asarray(logo, float)
        parr = np.asarray(pad, float)
        col_src = larr[src[:, 1].astype(int), src[:, 0].astype(int), :3]
        col_dst = parr[dst[:, 1].astype(int), dst[:, 0].astype(int), :3]
        src += (lx, ly)
        dst += (px, py)
        delay = rng.random(N) * 0.35                      # not all at once
        swirl = (rng.random(N) - 0.5) * 2                 # each point's own curve
        bright = 0.75 + rng.random(N) * 0.5

        frames = int(END * FPS)
        for f in range(frames):
            t = f / FPS
            canvas = Image.new("RGB", (W, H), BG)
            a_logo = phase(t, LOGO_IN) * (1 - phase(t, BREAK))
            if a_logo > 0:
                lay = logo.copy()
                lay.putalpha(lay.getchannel("A").point(lambda v, k=a_logo: int(v * k)))
                canvas.paste(lay, (lx, ly), lay)
            a_dots = phase(t, BREAK) * (1 - phase(t, FORM))
            if a_dots > 0:
                k = np.clip((t - FLY[0]) / (FLY[1] - FLY[0]) * 1.35 - delay, 0, 1)
                k = k * k * (3 - 2 * k)
                pos = src * (1 - k[:, None]) + dst * k[:, None]
                arc = np.sin(k * math.pi)                 # out of line in the middle of the flight
                pos[:, 0] += swirl * arc * 140
                pos[:, 1] -= arc * 90 * (0.4 + 0.6 * np.abs(swirl))
                col = (col_src * (1 - k[:, None]) + col_dst * k[:, None]) * bright[:, None]
                col = np.clip(col * (1 + 0.5 * arc[:, None]), 0, 255)
                acc = np.zeros((H, W, 3), float)
                xi = np.clip(pos[:, 0].astype(int), 0, W - 2)
                yi = np.clip(pos[:, 1].astype(int), 0, H - 2)
                for ox in (0, 1):
                    for oy in (0, 1):
                        np.maximum.at(acc, (yi + oy, xi + ox), col)
                dots = Image.fromarray(acc.astype(np.uint8), "RGB")
                glow = dots.filter(ImageFilter.GaussianBlur(6))
                base = np.asarray(canvas, float)
                out = base + (np.asarray(dots, float) + np.asarray(glow, float) * 0.9) * a_dots
                canvas = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
            a_pad = phase(t, FORM)
            if a_pad > 0:
                lay = pad.copy()
                lay.putalpha(lay.getchannel("A").point(lambda v, k=a_pad: int(v * k)))
                canvas.paste(lay, (px, py), lay)
            fade = 1 - phase(t, FADE_OUT)
            if fade < 1:
                canvas = Image.blend(Image.new("RGB", (W, H), BG), canvas, fade)
            canvas.save(tmp / f"f{f:04d}.png")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        # VP8 with a (silent) Vorbis sound track, 1280 wide: what Steam's movie player takes reliably. A VP9 video
        # without sound (the first version) did not play on the HP; people whose custom startup movie stayed black
        # fixed it by re-encoding to VP8 + Vorbis (ValveSoftware/steam-for-linux#11655). 16:9 kept for a TV.
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", tmp / "f%04d.png",
                        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                        "-c:v", "libvpx", "-b:v", "3M", "-vf", "scale=1280:720", "-pix_fmt", "yuv420p",
                        "-c:a", "libvorbis", "-b:a", "64k", "-shortest", OUT], check=True)
        if len(sys.argv) > 1:                             # a folder for a few still frames, to look at
            for name, f in (("logo", 40), ("break", 62), ("flight", 90), ("arrive", 115), ("controller", 150)):
                shutil.copy(tmp / f"f{f:04d}.png", Path(sys.argv[1]) / f"tv-intro-{name}.png")
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
