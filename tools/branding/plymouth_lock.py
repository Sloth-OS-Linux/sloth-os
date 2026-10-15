#!/usr/bin/env python3
"""A Plymouth-téma lakat ikonja (lock.png) a titkosított lemez jelszókérőjéhez (fejlesztői segéd).

A jelszókérő szövegét a systemd adja, angolul és technikai formában ("Please enter passphrase for disk
luks-…"), és az initramfs-ben nincs nyelvi beállítás a fordításhoz. Ezért a téma szöveg helyett ezt a
nyelvfüggetlen jelet mutatja a beírt karakterek pöttyei fölött.

Használat: python tools/branding/plymouth_lock.py   (felülírja a téma lock.png-jét)
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "files/system/usr/share/plymouth/themes/sloth-os/lock.png"
SIZE, SS = 128, 8  # végső méret, élsimításhoz ennyiszeres rajz
COLOR = (227, 229, 232, 255)  # mint a téma szövegei

s = SIZE * SS
img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
u = s / 128
# kengyel (ív a test fölött)
d.arc((34 * u, 10 * u, 94 * u, 72 * u), start=180, end=360, fill=COLOR, width=int(11 * u))
d.rectangle((34 * u, 40 * u, 45 * u, 62 * u), fill=COLOR)
d.rectangle((83 * u, 40 * u, 94 * u, 62 * u), fill=COLOR)
# test
d.rounded_rectangle((22 * u, 58 * u, 106 * u, 120 * u), radius=12 * u, fill=COLOR)
# kulcslyuk (átlátszó)
hole = Image.new("L", (s, s), 0)
h = ImageDraw.Draw(hole)
h.ellipse((55 * u, 76 * u, 73 * u, 94 * u), fill=255)
h.polygon([(59 * u, 88 * u), (69 * u, 88 * u), (72 * u, 108 * u), (56 * u, 108 * u)], fill=255)
img.putalpha(Image.composite(Image.new("L", (s, s), 0), img.getchannel("A"), hole))
img.resize((SIZE, SIZE), Image.LANCZOS).save(OUT, optimize=True)
print("kész:", OUT)
