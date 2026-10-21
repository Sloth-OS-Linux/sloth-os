"""Az rpm-ostree technikai üzeneteinek fordítása emberi nyelvre.

A felhasználó soha nem látja a nyers kimenetet; csak azt, hogy épp mi történik
("Frissítés letöltése…"). A nyers szöveg a naplóba kerül hibakereséshez.
A szövegek a választott nyelven jelennek meg (i18n.py).
"""
import datetime
from pathlib import Path

from PySide6.QtCore import QDate, QLocale, QTime

from .i18n import N_, catalog, tr

# (minta, szöveg) párok; az első egyező nyer. A minták kisbetűsek.
_STAGES = [
    (("rollback",), N_("Preparing to roll back…")),
    (("pulling manifest", "checking for updates", "receiving metadata", "scanning metadata",
      "resolving", "fetching manifest", "updating metadata"), N_("Looking for updates…")),
    (("importing", "unpacking", "checking out", "writing objects", "applying"),
     N_("Unpacking the update…")),
    (("fetching", "receiving objects", "receiving delta", "downloading", "pulling", "layer", "chunk"),
     N_("Downloading the update…")),
    (("staging deployment", "deploying", "writing", "regenerating initramfs", "running", "relabeling",
      "finalizing", "copying /etc", "bootloader"), N_("Preparing the update for restart…")),
    (("pruning", "cleanup", "cleaning", "freed"), N_("Cleaning up…")),
]

_ERRORS = [
    (("not authorized", "authentication", "permission denied", "polkit"),
     N_("This needs administrator approval. Try again and enter your password.")),
    (("no space", "enospc", "disk full"),
     N_("There isn't enough free disk space. Free up some space and try again.")),
    (("could not resolve", "network", "timed out", "timeout", "connection refused",
      "temporary failure", "unreachable", "tls", "dns"),
     N_("Couldn't reach the update server. Check your internet connection.")),
    (("transaction in progress", "already in progress", "busy"),
     N_("Another update is running in the background. We'll wait for it to finish.")),
    (("cancelled", "canceled"), N_("You cancelled the operation.")),
    # az aláírás-ellenőrzés (ostree-image-signed): pl. egy épp készülő, még alá nem írt verzió
    (("signature", "sigstore", "policy requirements"),
     N_("The latest update isn't available yet (it's being prepared right now). Try again in a few minutes.")),
]

GENERIC_ERROR = N_("Something went wrong. Try again later, or restart the computer.")
GENERIC_BUSY = N_("Working on it…")


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
    text = tr("{size} downloaded", size=size_text(transferred))
    if rate > 0:
        text += " · " + tr("{size}/s", size=size_text(rate))
    return text


def date_text(timestamp):
    """Dátum a választott nyelv szokása szerint (pl. "2026. október 13." / "October 13, 2026")."""
    if not timestamp:
        return ""
    d = datetime.datetime.fromtimestamp(int(timestamp))
    return QLocale(catalog.language()).toString(QDate(d.year, d.month, d.day), QLocale.FormatType.LongFormat)


def datetime_text(when):
    """Időpont röviden: "Ma 14:00", "Tegnap 09:00", különben "2026. október 13. 14:00" (helyi időben)."""
    local = when.astimezone()
    time = QLocale(catalog.language()).toString(QTime(local.hour, local.minute), QLocale.FormatType.ShortFormat)
    days = (datetime.date.today() - local.date()).days
    if days == 0:
        return tr("Today {time}", time=time)
    if days == 1:
        return tr("Yesterday {time}", time=time)
    return f"{date_text(local.timestamp())} {time}"


def _pretty_name(deployment):
    """A rendszerverzió saját nevéből (os-release PRETTY_NAME), pl. "Sloth OS 1.0 (Fedora Atomic 44)".

    A telepített verziók fájljai olvashatók (/ostree/deploy/...); a még le nem töltött frissítésnek nincs ilyen."""
    paths = [Path("/ostree/deploy", deployment.get("osname") or "",
                  "deploy", f"{deployment.get('checksum')}.{deployment.get('serial')}", "usr/lib/os-release")]
    if deployment.get("booted"):
        paths.append(Path("/usr/lib/os-release"))
    for path in paths:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            continue
    return ""


def version_text(deployment):
    """Pl. "Sloth OS 1.0 (Fedora Atomic 44) · 2026. október 13." a telepített verzióból."""
    if not deployment:
        return ""
    # Az rpm-ostree "version" címkéje ("44.20261013") csak a Fedora verziószáma, nem a Sloth OS-é
    name = _pretty_name(deployment) or "Sloth OS"
    date = date_text(deployment.get("timestamp"))
    return f"{name} · {date}" if date else name
