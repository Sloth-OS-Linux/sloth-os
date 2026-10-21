#!/usr/bin/env python3
"""The Plymouth theme's lock icon (lock.png) for the encrypted disk's password prompt (developer tool).

The password prompt's text comes from systemd, in English and in a technical form ("Please enter passphrase for disk
luks-…"), and the initramfs has no language setting for translating it. So instead of text the theme shows this
language-independent sign above the dots of the typed characters.

Usage: python tools/branding/plymouth_lock.py   (overwrites the theme's lock.png)
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "files/system/usr/share/plymouth/themes/sloth-os/lock.png"
SIZE, SS = 128, 8  # final size, drawn this many times bigger for anti-aliasing
COLOR = (227, 229, 232, 255)  # like the theme's texts

s = SIZE * SS
img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
u = s / 128
# shackle (an arc above the body)
d.arc((34 * u, 10 * u, 94 * u, 72 * u), start=180, end=360, fill=COLOR, width=int(11 * u))
d.rectangle((34 * u, 40 * u, 45 * u, 62 * u), fill=COLOR)
d.rectangle((83 * u, 40 * u, 94 * u, 62 * u), fill=COLOR)
# test
d.rounded_rectangle((22 * u, 58 * u, 106 * u, 120 * u), radius=12 * u, fill=COLOR)
# keyhole (transparent)
hole = Image.new("L", (s, s), 0)
h = ImageDraw.Draw(hole)
h.ellipse((55 * u, 76 * u, 73 * u, 94 * u), fill=255)
h.polygon([(59 * u, 88 * u), (69 * u, 88 * u), (72 * u, 108 * u), (56 * u, 108 * u)], fill=255)
img.putalpha(Image.composite(Image.new("L", (s, s), 0), img.getchannel("A"), hole))
img.resize((SIZE, SIZE), Image.LANCZOS).save(OUT, optimize=True)
print("done:", OUT)
