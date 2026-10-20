"""Népszerű Windowsos telepítők, amelyeknek van Linuxra készült változata (Flathub).

Ha a felhasználó egy ilyen .exe-t nyit meg, az .exe kezelő a Linuxos változatot ajánlja (a Windowsosat
mellette továbbra is telepítheti). Helyi lista, internet nélkül is működik; a fájl nevéből ismerjük fel
(ékezetek, kis- és nagybetűk, jelek nélkül, pl. "MSTeamsSetup.exe" -> "msteamssetup").

reason:
  "better"   a Windowsos változat is futhat, de a Linuxos jobban illeszkedik, és magától frissül
  "broken"   a Windowsos változat itt nem települ vagy nem fut megbízhatóan (pl. az új Teams .NET-es
             telepítője, 2026-10-20-i teszt)
  "heroic"   Epic Games és GOG: a hivatalos indítók helyett a Heroic (Linuxra készült indító, a játékokat ugyanúgy
             Protonnal futtatja); az Epic új telepítőjének aláírás-ellenőrzése Wine alatt elbukik (2026-10-20)
Új elem előtt: https://flathub.org/api/v2/appstream/<id> (200 = megvan)
"""
import re
import unicodedata

# (minta a normalizált fájlnévre, Flathub-azonosító, a Linuxos változat neve, ok)
NATIVE = [
    (r"msteams|teamssetup|teamsbootstrapper|teamsx64|teamswindows", "com.github.IsmaelMartinez.teams_for_linux",
     "Teams for Linux", "broken"),
    (r"epicinstaller|epicgameslauncher", "com.heroicgameslauncher.hgl", "Heroic", "heroic"),
    (r"goggalaxy|gogsetup|setupgalaxy", "com.heroicgameslauncher.hgl", "Heroic", "heroic"),
    (r"steamsetup", "com.valvesoftware.Steam", "Steam", "broken"),
    (r"discordsetup|^discord", "com.discordapp.Discord", "Discord", "better"),
    (r"spotify", "com.spotify.Client", "Spotify", "better"),
    (r"zoominstaller|zoomsetup|zoomusinstaller", "us.zoom.Zoom", "Zoom", "better"),
    (r"slacksetup|^slack", "com.slack.Slack", "Slack", "better"),
    (r"chromesetup|googlechrome|chromestandalone", "com.google.Chrome", "Google Chrome", "better"),
    (r"firefox", "org.mozilla.firefox", "Firefox", "better"),
    (r"microsoftedge|medgesetup|edgesetup", "com.microsoft.Edge", "Microsoft Edge", "better"),
    (r"bravebrowser|bravesetup", "com.brave.Browser", "Brave", "better"),
    (r"^opera(?!gx)|operasetup", "com.opera.Opera", "Opera", "better"),
    (r"vivaldi", "com.vivaldi.Vivaldi", "Vivaldi", "better"),
    (r"^vlc", "org.videolan.VLC", "VLC", "better"),
    (r"obsstudio", "com.obsproject.Studio", "OBS Studio", "better"),
    (r"telegram|^tsetup", "org.telegram.desktop", "Telegram", "better"),
    (r"signalsetup|^signal(?!rgb)", "org.signal.Signal", "Signal", "better"),
    (r"viber", "com.viber.Viber", "Viber", "better"),
    (r"elementsetup|elementdesktop", "im.riot.Riot", "Element", "better"),
    (r"thunderbird", "org.mozilla.Thunderbird", "Thunderbird", "better"),
    (r"libreoffice", "org.libreoffice.LibreOffice", "LibreOffice", "better"),
    (r"onlyoffice", "org.onlyoffice.desktopeditors", "ONLYOFFICE", "better"),
    (r"wpsoffice", "com.wps.Office", "WPS Office", "better"),
    (r"bitwarden", "com.bitwarden.desktop", "Bitwarden", "better"),
    (r"obsidian", "md.obsidian.Obsidian", "Obsidian", "better"),
    (r"^gimp", "org.gimp.GIMP", "GIMP", "better"),
    (r"^krita", "org.kde.krita", "Krita", "better"),
    (r"inkscape", "org.inkscape.Inkscape", "Inkscape", "better"),
    (r"^blender", "org.blender.Blender", "Blender", "better"),
    (r"audacity", "org.audacityteam.Audacity", "Audacity", "better"),
    (r"kdenlive", "org.kde.kdenlive", "Kdenlive", "better"),
    (r"vscodeusersetup|vscodesetup|visualstudiocode", "com.visualstudio.code", "Visual Studio Code", "better"),
    (r"anydesk", "com.anydesk.Anydesk", "AnyDesk", "better"),
    (r"rustdesk", "com.rustdesk.RustDesk", "RustDesk", "better"),
    (r"qbittorrent", "org.qbittorrent.qBittorrent", "qBittorrent", "better"),
    (r"prismlauncher", "org.prismlauncher.PrismLauncher", "Prism Launcher", "better"),
    (r"itchsetup|^itch", "io.itch.itch", "itch", "better"),
    (r"retroarch", "org.libretro.RetroArch", "RetroArch", "better"),
]
_COMPILED = [(re.compile(p), app_id, name, reason) for p, app_id, name, reason in NATIVE]


def normalize(name):
    plain = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", plain.rsplit(".", 1)[0] if plain.endswith((".exe", ".msi")) else plain)


def match(filename):
    """-> {"id", "name", "reason"} a Linuxos változatról, vagy None."""
    key = normalize(filename)
    if len(key) < 3:
        return None
    for pattern, app_id, name, reason in _COMPILED:
        if pattern.search(key):
            return {"id": app_id, "name": name, "reason": reason}
    return None
