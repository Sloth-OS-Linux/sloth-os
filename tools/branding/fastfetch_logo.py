#!/usr/bin/env python3
"""The Sloth OS logo for fastfetch, drawn with characters (like the Fedora logo in `fastfetch`).

Usage: python3 fastfetch_logo.py <flat logo png> <output txt> [width] [silver char] [face char]
  (render the PNG first: rsvg-convert -w 800 files/system/usr/share/sloth-os/logo/sloth-logo-flat.svg -o flat.png;
   output: files/system/usr/share/sloth-os/logo/sloth-ascii.txt)

The flat logo is a silver shape with holes (the light parts of the face). Like Fedora's white "f" on blue,
both are drawn: the silver parts with $1, the holes inside the head with $2 (the colors are set in fastfetch's
config.jsonc). Every character cell covers a 1:2 area of the image (a terminal cell is about twice as high as
wide). At the head's outline a lighter character is chosen by where the shape is in the cell (top: ', bottom:
, or ., a little: ; or :), so the outline stays smooth.
"""
import sys
from collections import deque

from PIL import Image, ImageFilter

OUTSIDE, SILVER, FACE = 0, 1, 2


def regions(img, close=25):
    """Per pixel: outside the head, a silver part, or a light part of the face.

    The head's outline is the silhouette closed with a 25 px (at 400 px wide) dilation and erosion, then filled:
    the light parts of the face reach the edge through the gaps between the fur's tufts, so a plain flood fill
    from the edge would leak into the face."""
    w, h = img.size
    silver = img.getchannel("A").point(lambda a: 255 if a > 127 else 0)
    closed = silver.filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(close))
    head = closed.load()
    s = silver.load()
    # the head: everything not reachable from the edge through pixels outside the closed outline
    outside = [[False] * w for _ in range(h)]
    queue = deque((x, y) for x in range(w) for y in (0, h - 1))
    queue.extend((x, y) for y in range(h) for x in (0, w - 1))
    while queue:
        x, y = queue.popleft()
        if 0 <= x < w and 0 <= y < h and not outside[y][x] and not head[x, y]:
            outside[y][x] = True
            queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return [[OUTSIDE if outside[y][x] else SILVER if s[x, y] else FACE for x in range(w)] for y in range(h)]


def edge_char(top, bottom, fill):
    """The character for a cell from how much of its upper and lower half is inside the head (0..1)."""
    if top < 0.15 and bottom < 0.15:
        return " "
    if top > 0.6 and bottom > 0.6:
        return fill
    if bottom > 0.6 and top < 0.3:
        return ","
    if top > 0.6 and bottom < 0.3:
        return "'"
    if top < 0.15:
        return "."
    if bottom < 0.15:
        return "`"
    return ";" if top + bottom > 0.9 else ":"


def main():
    src, out = sys.argv[1:3]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    fills = {SILVER: sys.argv[4] if len(sys.argv) > 4 else "c", FACE: sys.argv[5] if len(sys.argv) > 5 else "M"}
    img = Image.open(src).convert("RGBA")
    img = img.resize((400, round(400 * img.height / img.width)))
    kind = regions(img)
    cw = img.width / width
    rows = round(img.height / (cw * 2))

    lines = []
    for r in range(rows):
        text, color = "", ""
        for c in range(width):
            x0, x1 = int(c * cw), int((c + 1) * cw)
            y0, y1 = int(r * cw * 2), min(int((r + 1) * cw * 2), img.height)
            mid = (y0 + y1) // 2

            def count(ya, yb, which):
                return sum(kind[y][x] in which for x in range(x0, x1) for y in range(ya, yb))
            area = max(1, (x1 - x0) * (mid - y0)), max(1, (x1 - x0) * (y1 - mid))
            inside = (SILVER, FACE)
            top, bottom = count(y0, mid, inside) / area[0], count(mid, y1, inside) / area[1]
            region = SILVER if count(y0, y1, (SILVER,)) >= count(y0, y1, (FACE,)) else FACE
            ch = edge_char(top, bottom, fills[region])
            want = "" if ch == " " else ("$1" if region == SILVER else "$2")
            if want and want != color:
                text += want
                color = want
            text += ch
        lines.append(text.rstrip())
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
