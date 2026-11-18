#!/usr/bin/env python3
"""The desktop's loading screen after sign-in (KSplash): the Sloth OS logo drawn out of nothing in a circle, then it
pulses until the desktop is ready (developer tool, not in the image).

A point of silver light runs once around the middle of the screen, clockwise from the top, leaving a fading ring of
light behind it; the logo appears behind it as it goes, like a clock hand uncovering it. When the circle closes, the
ring fades away and the logo stays, exactly where and as big as Splash.qml shows its still logo, so Splash.qml switches
to it (and makes it pulse) without a jump. About 2.2 seconds; an animated WebP that plays once (Qt's WebP plugin plays
it). (Until 2026-11-18: "Sloth OS" written on the wall as a silver tag first; the user found it too busy.)

The picture is 1920 x 1080 with the logo LOGO_PX tall in its middle: Splash.qml scales it so the logo is as tall as
its still logo (on a 1080p screen 1:1, the whole screen).

Needs: python3-numpy, python3-pillow (ffmpeg for the preview video).
Usage: python3 tools/make_splash_intro.py [folder for still frames and a preview]
       (writes files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/contents/splash/images/intro.webp)
"""
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parent.parent
SPLASH = REPO / "files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/contents/splash/images"
OUT = SPLASH / "intro.webp"
LOGO = SPLASH / "logo.png"             # the very logo Splash.qml shows after the intro, so they match exactly

CW, CH, FPS = 1920, 1080, 30
LOGO_PX = 346                          # the logo's size in the picture: Splash.qml's logoSize on a 1080p screen
BG = np.array([28, 30, 33], float)     # #1c1e21, Splash.qml's background
LIGHT = np.array([236, 240, 245], float)
RING_R = LOGO_PX * 0.62                # the ring of light around the logo
RING_W = 2.2                           # its thickness (pixels, the soft core)
SOFT = 0.45                            # radians: how softly the logo's edge follows the light

# timeline (seconds)
SWEEP = (0.15, 1.55)                   # the light runs once around
RING_OUT = (1.45, 2.05)                # the ring fades away
END = 2.2


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def phase(t, span):
    a, b = span
    return ease((t - a) / (b - a))


def main():
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    logo = np.asarray(Image.open(LOGO).convert("RGBA").resize((LOGO_PX, LOGO_PX), Image.LANCZOS), float)

    # the working area: a square around the middle, big enough for the ring and its glow
    half = int(RING_R + 60)
    cx, cy = CW // 2, CH // 2
    yy, xx = np.mgrid[-half:half, -half:half].astype(float) + 0.5
    r = np.hypot(xx, yy)
    theta = np.mod(np.arctan2(xx, -yy), 2 * math.pi)           # 0 at the top, growing clockwise
    ring = np.exp(-((r - RING_R) / RING_W) ** 2)
    lo = half - LOGO_PX // 2                                   # the logo's place in the working area
    la = np.zeros((2 * half, 2 * half))
    lc = np.zeros((2 * half, 2 * half, 3))
    la[lo:lo + LOGO_PX, lo:lo + LOGO_PX] = logo[..., 3] / 255
    lc[lo:lo + LOGO_PX, lo:lo + LOGO_PX] = logo[..., :3]

    def frame(area):
        canvas = np.empty((CH, CW, 3))
        canvas[:] = BG
        canvas[cy - half:cy + half, cx - half:cx + half] = area
        return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB")

    frames = []
    n = int(round(END * FPS))
    for f in range(n + 1):
        t = f / FPS
        s = (2 * math.pi + SOFT) * phase(t, SWEEP)              # where the light is (radians from the top)
        area = np.empty((2 * half, 2 * half, 3))
        area[:] = BG
        if f == n:                                             # the last frame: the still logo, nothing else
            area = area * (1 - la[..., None]) + lc * la[..., None]
            frames.append(frame(area))
            break
        # the logo, uncovered behind the light
        cover = np.clip((s - theta) / SOFT, 0, 1) * la
        area = area * (1 - cover[..., None]) + lc * cover[..., None]
        # the ring of light: bright at the head, fading behind it; all of it fades out at the end
        behind = s - theta
        trail = np.where(behind >= 0, np.exp(-behind / 2.2), 0.0)
        glow = ring * trail * (1 - phase(t, RING_OUT))
        if s < 2 * math.pi:                                    # the head: a brighter point of light
            hx, hy = RING_R * math.sin(s), -RING_R * math.cos(s)
            glow = glow + 1.3 * np.exp(-((xx - hx) ** 2 + (yy - hy) ** 2) / (2 * 5.0 ** 2))
        g = Image.fromarray(np.clip(glow * 255, 0, 255).astype(np.uint8), "L")
        halo = np.asarray(g.filter(ImageFilter.GaussianBlur(10)), float) / 255
        light = np.clip(glow + halo * 1.4, 0, 1.6)
        area = area + (LIGHT - area) * np.clip(light, 0, 1)[..., None]
        frames.append(frame(area))
        print(f"\r{f + 1}/{n + 1}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=round(1000 / FPS), loop=1,
                   quality=85, method=6)
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB, {len(frames)} frames)")
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
        for old in shots.glob("splash-*"):
            old.unlink()
        for name, sec in (("quarter", 0.5), ("half", 0.85), ("closing", 1.45), ("logo", END)):
            frames[min(len(frames) - 1, int(sec * FPS))].save(shots / f"splash-{name}.png")
        if shutil.which("ffmpeg"):   # a preview to watch: the intro, then 3 s of Splash.qml's pulse
            tmp = shots / "frames"
            tmp.mkdir(exist_ok=True)
            logo_img = Image.open(LOGO).convert("RGBA")
            pulse = []
            for k in range(3 * FPS):     # Splash.qml: 1.0 -> 1.06 -> 1.0 and opacity 1 -> 0.78 -> 1 in 1.6 s
                p = (1 - math.cos(2 * math.pi * k / (1.6 * FPS))) / 2
                size = int(round(LOGO_PX * (1 + 0.06 * p)))
                c = Image.new("RGB", (CW, CH), tuple(int(v) for v in BG))
                lg = logo_img.resize((size, size), Image.LANCZOS)
                lg.putalpha(lg.getchannel("A").point(lambda v, k=1 - 0.22 * p: int(v * k)))
                c.paste(lg, ((CW - size) // 2, (CH - size) // 2), lg)
                pulse.append(c)
            for k, fr in enumerate(frames + pulse):
                fr.save(tmp / f"{k:04d}.png")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(tmp / "%04d.png"),
                            "-c:v", "libvpx-vp9", "-b:v", "6M", "-pix_fmt", "yuv420p", str(shots / "splash-preview.webm")],
                           check=True)
            shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
