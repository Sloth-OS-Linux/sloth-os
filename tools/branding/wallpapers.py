#!/usr/bin/env python3
"""Turns wallpapers into Plasma packages (files/system/usr/share/wallpapers/SlothOS-*).

Preparation (in the work folder): in/<name>.png the original pictures with ASCII names, up/<name>.png the
Real-ESRGAN (realesrgan-x4plus) 4x upscaled version, titles.json: {name: displayed (English) title}.
Usage: python3 wallpapers.py <output folder>
Output: 3840x2160.jpg (+ 5120x2160.jpg for ultrawide pictures), a 60% AI + 40% Lanczos mix.
"""
import json
import os
import subprocess
import sys

W = os.getcwd()
titles = json.load(open("titles.json"))
OUT = sys.argv[1]
# Where to cut the 16:9 crop for ultrawide pictures (0 = left edge, 0.5 = middle, 1 = right edge)
OFFSET = {"lusta-esti-sloth-gamer-kuckoja": 0.78}

def run(*a):
    subprocess.run(["magick", *a], check=True)

def size(p):
    w, h = subprocess.run(["magick", "identify", "-format", "%w %h", p], capture_output=True, text=True).stdout.split()
    return int(w), int(h)

def render(slug, tw, th, dest, offset=0.5):
    """60% AI upscaling + 40% Lanczos, filled and cropped to the target size."""
    w, h = size(f"in/{slug}.png")
    scale = max(tw / w, th / h)
    rw, rh = round(w * scale), round(h * scale)
    x = round((rw - tw) * offset); y = (rh - th) // 2
    geo = f"{tw}x{th}+{x}+{y}"
    run(f"up/{slug}.png", "-filter", "Lanczos", "-resize", f"{rw}x{rh}!", "-crop", geo, "+repage", "/tmp/_e.png")
    run(f"in/{slug}.png", "-filter", "Lanczos", "-resize", f"{rw}x{rh}!", "-crop", geo, "+repage", "/tmp/_l.png")
    run("/tmp/_e.png", "/tmp/_l.png", "-compose", "blend", "-define", "compose:args=60", "-composite",
        "-unsharp", "0x0.8+0.4+0.02", "-strip", "-sampling-factor", "4:2:0", "-quality", "90", dest)

for slug, title in titles.items():
    w, h = size(f"in/{slug}.png")
    ultrawide = w / h > 2.0
    pkg = os.path.join(OUT, f"SlothOS-{slug}")
    img = os.path.join(pkg, "contents", "images")
    os.makedirs(img, exist_ok=True)
    render(slug, 3840, 2160, os.path.join(img, "3840x2160.jpg"), OFFSET.get(slug, 0.5))
    if ultrawide:
        render(slug, 5120, 2160, os.path.join(img, "5120x2160.jpg"))
    # the wallpapers' license: CC BY-SA 4.0 (see NOTICE)
    meta = {"KPlugin": {"Id": f"SlothOS-{slug}", "Name": title, "Authors": [{"Name": "Sloth OS"}],
                        "License": "CC-BY-SA-4.0"}}
    json.dump(meta, open(os.path.join(pkg, "metadata.json"), "w"), ensure_ascii=False, indent=4)
    print(("UW " if ultrawide else "   ") + slug)
