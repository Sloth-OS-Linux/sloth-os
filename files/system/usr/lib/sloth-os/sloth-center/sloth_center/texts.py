"""Translating rpm-ostree's technical messages into plain language.

The user never sees the raw output; only what is happening right now
("Downloading the update…"). The raw text goes to the log for debugging.
The texts appear in the chosen language (i18n.py).
"""
import datetime
from pathlib import Path

from PySide6.QtCore import QDate, QLocale, QTime

from .i18n import N_, catalog, tr

# (pattern, text) pairs; the first match wins. The patterns are lowercase.
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
    # signature verification (ostree-image-signed): e.g. a version being built right now, not signed yet
    (("signature", "sigstore", "policy requirements"),
     N_("The latest update isn't available yet (it's being prepared right now). Try again in a few minutes.")),
]

GENERIC_ERROR = N_("Something went wrong. Try again later, or restart the computer.")
GENERIC_BUSY = N_("Working on it…")


def stage_text(raw, current=None):
    """A human text from the technical step name. If we do not know it, the previous one stays."""
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
    """A date in the chosen language's style (e.g. "2026. október 13." / "October 13, 2026")."""
    if not timestamp:
        return ""
    d = datetime.datetime.fromtimestamp(int(timestamp))
    return QLocale(catalog.language()).toString(QDate(d.year, d.month, d.day), QLocale.FormatType.LongFormat)


def datetime_text(when):
    """A short time: "Today 14:00", "Yesterday 09:00", otherwise "October 13, 2026 14:00" (in local time)."""
    local = when.astimezone()
    time = QLocale(catalog.language()).toString(QTime(local.hour, local.minute), QLocale.FormatType.ShortFormat)
    days = (datetime.date.today() - local.date()).days
    if days == 0:
        return tr("Today {time}", time=time)
    if days == 1:
        return tr("Yesterday {time}", time=time)
    return f"{date_text(local.timestamp())} {time}"


def _pretty_name(deployment):
    """From the system version's own name (os-release PRETTY_NAME), e.g. "Sloth OS 1.0.2 (Fedora Atomic 44)".

    The installed versions' files are readable (/ostree/deploy/...); an update not downloaded yet has none."""
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
    """E.g. "Sloth OS 1.0.2 (Fedora Atomic 44) · October 13, 2026" from the installed version."""
    if not deployment:
        return ""
    # rpm-ostree's "version" label ("44.20261013") is only Fedora's version number, not Sloth OS's
    name = _pretty_name(deployment) or "Sloth OS"
    date = date_text(deployment.get("timestamp"))
    return f"{name} · {date}" if date else name
