#!/usr/bin/env python3
"""The Sloth OS logo (the hanging sloth of the Start menu) for fastfetch, drawn with characters, like the Fedora
logo in `fastfetch`.

Usage: python3 fastfetch_logo.py tools/branding/sloth-ascii-art.txt files/system/usr/share/sloth-os/logo/sloth-ascii.txt

The drawing (sloth-ascii-art.txt) is made by hand after files/system/usr/share/icons/hicolor/scalable/apps/sloth-os.svg:
converted automatically, the icon's thin arms melt into the head at this size. This script only adds the
colors: "M" is the light mask and leaf ($2), "o" the grey belly ($3), everything else the sloth and the branch
($1, silver: the icon's dark color would not show on a dark terminal). The colors themselves are set in
fastfetch's config.jsonc.
"""
import sys

COLOR = {"M": "$2", "o": "$3"}


def colorize(line):
    out, current = "", ""
    for ch in line.rstrip():
        want = "" if ch == " " else COLOR.get(ch, "$1")
        if want and want != current:
            out += want
            current = want
        out += ch
    return out


def main():
    src, dst = sys.argv[1:3]
    with open(src, encoding="utf-8") as f:
        lines = [colorize(line) for line in f.read().splitlines()]
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
