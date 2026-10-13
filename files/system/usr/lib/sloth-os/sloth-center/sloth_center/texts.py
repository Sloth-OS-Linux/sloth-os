"""Az rpm-ostree technikai üzeneteinek fordítása emberi nyelvre.

A felhasználó soha nem látja a nyers kimenetet; csak azt, hogy épp mi történik
("Frissítés letöltése…"). A nyers szöveg a naplóba kerül hibakereséshez.
"""
import datetime
import re

# (minta, szöveg) párok; az első egyező nyer. A minták kisbetűsek.
_STAGES = [
    (("rollback",), "Visszaállítás előkészítése…"),
    (("pulling manifest", "checking for updates", "receiving metadata", "scanning metadata",
      "resolving", "fetching manifest", "updating metadata"), "Frissítés keresése…"),
    (("importing", "unpacking", "checking out", "writing objects", "applying"),
     "Frissítés kicsomagolása…"),
    (("fetching", "receiving objects", "receiving delta", "downloading", "pulling", "layer", "chunk"),
     "Frissítés letöltése…"),
    (("staging deployment", "deploying", "writing", "regenerating initramfs", "running", "relabeling",
      "finalizing", "copying /etc", "bootloader"), "Frissítés előkészítése az újraindításhoz…"),
    (("pruning", "cleanup", "cleaning", "freed"), "Takarítás…"),
]

_ERRORS = [
    (("not authorized", "authentication", "permission denied", "polkit"),
     "Ehhez rendszergazdai jóváhagyás kell. Próbáld újra, és add meg a jelszavad."),
    (("no space", "enospc", "disk full"),
     "Nincs elég szabad hely a lemezen. Szabadíts fel helyet, és próbáld újra."),
    (("could not resolve", "network", "timed out", "timeout", "connection refused",
      "temporary failure", "unreachable", "tls", "dns"),
     "Nem sikerült elérni a frissítési szervert. Ellenőrizd az internetkapcsolatot."),
    (("transaction in progress", "already in progress", "busy"),
     "Egy másik frissítés éppen fut a háttérben. Megvárjuk, amíg végez."),
    (("cancelled", "canceled"), "A műveletet megszakítottad."),
]

GENERIC_ERROR = "Valami nem sikerült. Próbáld újra később, vagy indítsd újra a gépet."
GENERIC_BUSY = "Dolgozom rajta…"

_MONTHS = ["január", "február", "március", "április", "május", "június", "július",
           "augusztus", "szeptember", "október", "november", "december"]


def stage_text(raw, current=GENERIC_BUSY):
    """A technikai lépésnévből emberi szöveg. Ha nem ismerjük, marad az előző."""
    low = (raw or "").lower()
    for patterns, text in _STAGES:
        if any(p in low for p in patterns):
            return text
    return current


def error_text(raw):
    low = (raw or "").lower()
    for patterns, text in _ERRORS:
        if any(p in low for p in patterns):
            return text
    return GENERIC_ERROR


def size_text(nbytes):
    for unit, div in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("kB", 1024)):
        if nbytes >= div:
            value = nbytes / div
            return f"{value:.1f} {unit}".replace(".", ",") if value < 10 else f"{value:.0f} {unit}"
    return f"{nbytes} B"


def download_text(transferred, rate):
    if transferred <= 0:
        return ""
    text = f"{size_text(transferred)} letöltve"
    if rate > 0:
        text += f" · {size_text(rate)}/mp"
    return text


def date_text(timestamp):
    if not timestamp:
        return ""
    d = datetime.datetime.fromtimestamp(int(timestamp))
    return f"{d.year}. {_MONTHS[d.month - 1]} {d.day}."


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
