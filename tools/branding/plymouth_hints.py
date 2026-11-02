#!/usr/bin/env python3
"""The Plymouth theme's password hints (hint-<language>.png), one per installer language (developer tool).

Below the encrypted disk's password field the boot screen says what it waits for ("Type your disk password, then
press Enter") in the language chosen in the installer. The initramfs has no fonts for every script (Chinese, Tamil,
Arabic…), so the texts are drawn here, with the full font set and Qt's text shaping, into pictures. The text comes
from the installer's translations (boot.password_hint).

Usage: QT_QPA_PLATFORM=offscreen python tools/branding/plymouth_hints.py   (needs PySide6; rewrites the pictures)
"""
import json
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QPainter

REPO = Path(__file__).resolve().parents[2]
TRANSLATIONS = REPO / "iso/files/usr/lib/sloth-os/sloth-installer/sloth_installer/translations"
OUT = REPO / "files/system/usr/share/plymouth/themes/sloth-os"
KEY = "boot.password_hint"
PIXELS = 48                          # the text's size; the theme scales the picture to the screen
COLOR = QColor(227, 229, 232, 200)   # like the theme's texts, a little dimmer than the lock


def render(text, rtl):
    font = QFont("Noto Sans")
    font.setPixelSize(PIXELS)
    metrics = QFontMetricsF(font)
    width = int(metrics.horizontalAdvance(text)) + PIXELS
    height = int(metrics.height() * 1.4)
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.TextAntialiasing)
    painter.setFont(font)
    painter.setPen(COLOR)
    painter.setLayoutDirection(Qt.RightToLeft if rtl else Qt.LeftToRight)
    painter.drawText(QRectF(0, 0, width, height), Qt.AlignCenter, text)
    painter.end()
    return image


def main():
    QGuiApplication(sys.argv)
    written = 0
    for path in sorted(TRANSLATIONS.glob("*.json")):
        text = json.loads(path.read_text(encoding="utf-8")).get(KEY)
        if not text:
            print(f"{path.stem}: no {KEY}", file=sys.stderr)
            continue
        image = render(text, rtl=path.stem in ("ar", "he"))
        if not image.save(str(OUT / f"hint-{path.stem}.png"), "PNG"):
            sys.exit(f"could not write hint-{path.stem}.png")
        written += 1
    print(f"done: {written} pictures in {OUT}")


if __name__ == "__main__":
    main()
