"""Az rpm-ostree technikai üzeneteinek fordítása emberi nyelvre.

A felhasználó soha nem látja a nyers kimenetet; csak azt, hogy épp mi történik
("Frissítés letöltése…"). A nyers szöveg a naplóba kerül hibakereséshez.
A szövegek a választott nyelven jelennek meg (i18n.py).
"""
import datetime
import re

from PySide6.QtCore import QDate, QLocale

from .i18n import N_, catalog, tr

# (minta, szöveg) párok; az első egyező nyer. A minták kisbetűsek.
_STAGES = [
    (("rollback",), N_("Visszaállítás előkészítése…")),
    (("pulling manifest", "checking for updates", "receiving metadata", "scanning metadata",
      "resolving", "fetching manifest", "updating metadata"), N_("Frissítés keresése…")),
    (("importing", "unpacking", "checking out", "writing objects", "applying"),
     N_("Frissítés kicsomagolása…")),
    (("fetching", "receiving objects", "receiving delta", "downloading", "pulling", "layer", "chunk"),
     N_("Frissítés letöltése…")),
    (("staging deployment", "deploying", "writing", "regenerating initramfs", "running", "relabeling",
      "finalizing", "copying /etc", "bootloader"), N_("Frissítés előkészítése az újraindításhoz…")),
    (("pruning", "cleanup", "cleaning", "freed"), N_("Takarítás…")),
]

_ERRORS = [
    (("not authorized", "authentication", "permission denied", "polkit"),
     N_("Ehhez rendszergazdai jóváhagyás kell. Próbáld újra, és add meg a jelszavad.")),
    (("no space", "enospc", "disk full"),
     N_("Nincs elég szabad hely a lemezen. Szabadíts fel helyet, és próbáld újra.")),
    (("could not resolve", "network", "timed out", "timeout", "connection refused",
      "temporary failure", "unreachable", "tls", "dns"),
     N_("Nem sikerült elérni a frissítési szervert. Ellenőrizd az internetkapcsolatot.")),
    (("transaction in progress", "already in progress", "busy"),
     N_("Egy másik frissítés éppen fut a háttérben. Megvárjuk, amíg végez.")),
    (("cancelled", "canceled"), N_("A műveletet megszakítottad.")),
]

GENERIC_ERROR = N_("Valami nem sikerült. Próbáld újra később, vagy indítsd újra a gépet.")
GENERIC_BUSY = N_("Dolgozom rajta…")


def stage_text(raw, current=None):
    """A technikai lépésnévből emberi szöveg. Ha nem ismerjük, marad az előző."""
    low = (raw or "").lower()
    for patterns, text in _STAGES:
        if any(p in low for p in patterns):
            return tr(text)
    return current or tr(GENERIC_BUSY)


def error_text(raw):
    low = (raw or "").lower()
    for patterns, text in _ERRORS:
        if any(p in low for p in patterns):
            return tr(text)
    return tr(GENERIC_ERROR)


def size_text(nbytes):
    for unit, div in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("kB", 1024)):
        if nbytes >= div:
            value = nbytes / div
            return f"{value:.1f} {unit}".replace(".", ",") if value < 10 else f"{value:.0f} {unit}"
    return f"{nbytes} B"


def download_text(transferred, rate):
    if transferred <= 0:
        return ""
    text = tr("{size} letöltve", size=size_text(transferred))
    if rate > 0:
        text += " · " + tr("{size}/mp", size=size_text(rate))
    return text


def date_text(timestamp):
    """Dátum a választott nyelv szokása szerint (pl. "2026. október 13." / "October 13, 2026")."""
    if not timestamp:
        return ""
    d = datetime.datetime.fromtimestamp(int(timestamp))
    return QLocale(catalog.language()).toString(QDate(d.year, d.month, d.day), QLocale.FormatType.LongFormat)


def version_text(deployment):
    """Pl. "Sloth OS 44 · 2026. október 13." a telepített verzióból."""
    if not deployment:
        return ""
    version = str(deployment.get("version") or "")
    # A ublue verziók formája: "44.20261013" vagy "latest-44.20261013.0"
    m = re.search(r"(\d{2})\.(\d{8})", version)
    major = m.group(1) if m else ""
    date = date_text(deployment.get("timestamp"))
    name = f"Sloth OS {major}".strip()
    return f"{name} · {date}" if date else name
