#!/usr/bin/env python3
"""After a release's installer ISO is built: everything that needs its checksum and size, in one go.

    python tools/release-finish.py 1.4.1 out/release-1.4.1/sloth-os.iso [--site ../sloth-os-linux.github.io]

1. The ISO gets its SourceForge name (sloth-os-<version>-x86_64.iso, in the same folder), and next to it
   its .sha256, a .torrent (4 MiB pieces, the usual trackers, SourceForge as a web seed) and SourceForge's
   README.txt (a short description, then the release notes from docs/releases/<version>.md).
2. README.md: the "Current release" paragraph points to the new ISO (the "Coming soon" one goes).
3. docs/releases/<version>.md: the download line gets the links and the checksum.
4. With --site: the website's download page (button, checksum, release notes on top), the home page and the FAQ.

Nothing is uploaded or committed: at the end it prints the SourceForge upload and what to commit. The website's
download button should go live only when the ISO's /download link answers (mirrors need a few minutes).
"""
import argparse
import datetime
import hashlib
import html
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SF = "https://sourceforge.net/projects/sloth-os/files"
TRACKERS = ["udp://tracker.opentrackr.org:1337/announce", "udp://open.demonii.com:1337/announce",
            "udp://tracker.torrent.eu.org:451/announce", "udp://exodus.desync.com:6969/announce"]
PIECE = 4 * 1024 * 1024
INTRO = """Sloth OS {version}
{underline}

A Linux desktop for everyday use and gaming that feels familiar from the first boot: no terminal required.
Website and installation guide: https://sloth-os-linux.github.io/download.html

Download: {name} ({size}), or the .torrent next to it. The same file works for every computer; on a computer
with a newer NVIDIA graphics card, Sloth OS switches to its NVIDIA version by itself after installing.

SHA-256: {sha}
On Windows: (Get-FileHash .\\{name}).Hash

Already running Sloth OS? You get {version} as a normal, small update, no reinstall needed.

What Sloth OS can do
--------------------
- Feels familiar from the first minute: a taskbar that looks like Windows 10, Windows 11, Windows 7, a Mac, Ubuntu,
  ChromeOS or a floating bar, and a color scheme, chosen in the welcome wizard or any time later. Nothing is
  preinstalled: the Sloth Welcome wizard lets you pick your apps and installs them for you. Every text is available
  in 50 languages.
- One place for settings, Sloth Center: updates, disks, file backup and restore, folder sharing, displays, sound,
  Bluetooth, Wi-Fi, controllers, startup programs, app permissions, a security overview, network folders, system
  health, Feedback and offline Help.
- Games that just work: Steam, Proton, GameMode and gamescope are ready, with an FPS and temperature display per
  game, controller support, and the NVIDIA driver set up by itself.
- Windows programs without fuss: double-click an .exe, .msi or a disc image and it installs or runs.
- Safe, quiet updates: the system updates itself in the background as one piece and switches over at the next
  restart, and the previous version is one click away.
- An installer that explains itself: the whole disk or next to Windows, optional disk encryption, and a progress
  bar with plain sentences instead of scrolling text.

Requirements: a 64-bit PC that starts in UEFI mode, 4 GB of memory (16 GB for games), 64 GB of disk space,
and a USB stick of 8 GB or more for the installer.

Feedback: Sloth Center -> Feedback. Source code: https://github.com/Sloth-OS-Linux/sloth-os


========================================================================================================
Release notes: what is new in {version} ({date})
========================================================================================================
"""


def bencode(v):
    if isinstance(v, int):
        return b"i%de" % v
    if isinstance(v, str):
        v = v.encode()
    if isinstance(v, bytes):
        return b"%d:%s" % (len(v), v)
    if isinstance(v, list):
        return b"l" + b"".join(bencode(x) for x in v) + b"e"
    if isinstance(v, dict):
        return b"d" + b"".join(bencode(k) + bencode(v[k]) for k in sorted(v)) + b"e"
    raise TypeError(v)


def hash_and_torrent(iso, version):
    """The SHA-256 and the .torrent, reading the ISO once."""
    pieces, sha = bytearray(), hashlib.sha256()
    with iso.open("rb") as f:
        while block := f.read(PIECE):
            pieces += hashlib.sha1(block).digest()
            sha.update(block)
    torrent = {
        "announce": TRACKERS[0],
        "announce-list": [[t] for t in TRACKERS],
        "comment": "Sloth OS installer ISO",
        "created by": "Sloth OS",
        "creation date": int(time.time()),
        "url-list": [f"https://downloads.sourceforge.net/project/sloth-os/{version}/{iso.name}"],
        "info": {"length": iso.stat().st_size, "name": iso.name, "piece length": PIECE, "pieces": bytes(pieces)},
    }
    Path(f"{iso}.torrent").write_bytes(bencode(torrent))
    return sha.hexdigest()


def read(path):
    """The text with \\n line ends (a Windows checkout with core.autocrlf has \\r\\n); write() puts them back."""
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def write(path, text):
    if path.exists() and b"\r\n" in path.read_bytes():
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def replace_once(path, pattern, new, flags=0):
    text = read(path)
    text, n = re.subn(pattern, lambda m: new, text, count=1, flags=flags)
    if n != 1:
        sys.exit(f"ERROR: {path.name}: not found: {pattern[:80]}")
    write(path, text)


def notes_date(notes):
    m = re.search(r"^\*(.+?)\*$", notes, re.M)
    d = datetime.date.today()
    return m.group(1) if m else f"{d:%B} {d.day}, {d.year}"


def notes_sections(notes):
    """The release notes' own sections (not the known rough edges or the requirements): [(title, [items])]."""
    out = []
    for block in re.split(r"^## ", notes, flags=re.M)[1:]:
        title, _, body = block.partition("\n")
        if title.strip() in ("Known rough edges", "Requirements"):
            continue
        # an item ends at an empty line (the closing "Every new text…" sentence is not part of it)
        items = [" ".join(re.sub(r"\n\n.*", "", i, flags=re.S).split()) for i in re.split(r"^- ", body, flags=re.M)[1:]]
        out.append((title.strip(), items or [" ".join(body.split())]))
    return out


def plain(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text.replace("→", "->").replace("`", "")


def wrap(text, indent="  ", width=115):
    words, lines, line = text.split(), [], ""
    for w in words:
        if line and len(line) + 1 + len(w) > width:
            lines.append(line)
            line = indent + w
        else:
            line = f"{line} {w}" if line else w
    return "\n".join(lines + [line])


def to_html(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("version")
    ap.add_argument("iso", type=Path)
    ap.add_argument("--site", type=Path, help="the website repository (sloth-os-linux.github.io)")
    a = ap.parse_args()
    v = a.version
    notes_path = REPO / "docs/releases" / f"{v}.md"
    if not notes_path.exists():
        sys.exit(f"ERROR: no release notes: {notes_path}")
    notes = read(notes_path)
    date = notes_date(notes)

    iso = a.iso.resolve()
    name = f"sloth-os-{v}-x86_64.iso"
    if iso.name != name:
        target = iso.with_name(name)
        iso = iso.rename(target)
    print(f"ISO: {iso}")
    size = f"{iso.stat().st_size / 1e9:.1f} GB"
    print("Checksum and torrent (a few minutes)...")
    sha = hash_and_torrent(iso, v)
    write(Path(f"{iso}.sha256"), f"{sha}  {name}\n")
    base = f"{SF}/{v}/{name}"

    readme_txt = INTRO.format(version=v, underline="=" * len(f"Sloth OS {v}"), name=name, size=size, sha=sha, date=date)
    for title, items in notes_sections(notes):
        for item in items:
            readme_txt += wrap(f"- {plain(title)}: {plain(item)}") + "\n"
    write(iso.with_name("README.txt"), readme_txt)

    # README.md: the current release, and no "Coming soon" for it any more
    readme = REPO / "README.md"
    replace_once(readme, r"\*\*Current release: Sloth OS .*?(?=\n## What Sloth OS can do)",
                 f"**Current release: Sloth OS {v}** ({date}). Machines already running Sloth OS get it as a normal\n"
                 f"update. Download: [{name}]({base}/download) ({size}, also as a\n"
                 f"[torrent]({base}.torrent/download)), SHA-256 `{sha}`. What changed:\n"
                 f"[release notes](#release-notes) below (also in [docs/releases/{v}.md](docs/releases/{v}.md)).\n",
                 re.S)
    # docs/releases/<version>.md: the download line
    replace_once(notes_path, r"\*\*Download:\*\*.*?(?=\[Installation guide\])",
                 f"**Download:** [{name}]({base}/download)\n({size}) · [torrent]({base}.torrent/download) · "
                 f"SHA-256 `{sha}` ·\n", re.S)

    if a.site:
        docs = a.site / "docs"
        dl = docs / "download.html"
        old = re.search(r"Sloth OS ([0-9.]+) · available", read(dl)).group(1)
        replace_once(dl, r"Sloth OS [0-9.]+ · available", f"Sloth OS {v} · available")
        replace_once(dl, r"Sloth OS [0-9.]+ is ready\.", f"Sloth OS {v} is ready.")
        replace_once(dl, r'<a class="button button-primary" href="[^"]+">Download Sloth OS .*?SHA-256 checksum</a>',
                     f'<a class="button button-primary" href="{base}/download">Download Sloth OS {v} ({size}) ↗</a> '
                     f'<a href="{base}.torrent/download">Torrent</a> · <a href="{base}.sha256/download">SHA-256 '
                     f'checksum</a>')
        replace_once(dl, r"<code>[0-9a-f]{64}</code>", f"<code>{sha}</code>")
        replace_once(dl, r"Get-FileHash \.\\\\sloth-os-[0-9.]+-x86_64\.iso", f"Get-FileHash .\\\\{name}")
        replace_once(dl, r"Already running Sloth OS\? You get [0-9.]+ as", f"Already running Sloth OS? You get {v} as")
        items = "".join(f"<li><strong>{to_html(t)}:</strong> {' '.join(to_html(i) for i in its)}</li>"
                        for t, its in notes_sections(notes))
        text = read(dl)
        head = '<h2 id="whats-new">Release notes</h2><details open>'
        if head not in text:
            sys.exit("ERROR: download.html: the release notes heading has changed")
        text = text.replace(head, '<h2 id="whats-new">Release notes</h2>'
                            f"<details open><summary>What is new in {v} ({date})</summary><ul>{items}"
                            "<li>Every new text is available in all 50 languages.</li></ul></details><details>", 1)
        write(dl, text)
        for page in ("index.html", "faq.html"):
            p = docs / page
            # only the current release's mentions ("Sloth OS 1.0 was the first public release" stays)
            write(p, re.sub(rf"Sloth OS {re.escape(old)}(?![0-9.])", f"Sloth OS {v}", read(p)))

    print(f"""
Done: {name} ({size})
SHA-256: {sha}

1. Upload to SourceForge (the folder {v} is made if it is missing):
   sftp -i ~/.ssh/sloth-os-sourceforge -b - slothos@frs.sourceforge.net <<'SFTP'
   -mkdir /home/frs/project/sloth-os/{v}
   put "{iso.as_posix()}" /home/frs/project/sloth-os/{v}/
   put "{iso.as_posix()}.sha256" /home/frs/project/sloth-os/{v}/
   put "{iso.as_posix()}.torrent" /home/frs/project/sloth-os/{v}/
   put "{iso.with_name('README.txt').as_posix()}" /home/frs/project/sloth-os/{v}/
   SFTP
2. Wait until {base}/download answers (a few minutes), then commit and push README.md and
   docs/releases/{v}.md here{', and the website' if a.site else ''}.
3. GitHub release: gh release create v{v} --title "Sloth OS {v}" --notes-file docs/releases/{v}.md""")


if __name__ == "__main__":
    main()
