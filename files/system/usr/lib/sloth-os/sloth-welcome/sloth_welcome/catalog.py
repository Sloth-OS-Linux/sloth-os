"""A varázslóban felkínált appok. Alapból semmi nincs kiválasztva: a felhasználó dönt.

A kategóriák neve és leírása, valamint az appok rövid leírása a fordításokban van
(translations/<nyelv>.json: "category.<id>.name", "category.<id>.hint", "app.<id>").
Az appok neve márkanév, azt nem fordítjuk.

Minden app Flatpak a Flathubról, kivéve ahol `source` mást mond. Az ikonok
helyben vannak (/usr/share/sloth-os/welcome/icons/<id>.png), így a lista
internet nélkül is rendesen néz ki.

Új app felvétele előtt ellenőrizd, hogy létezik-e a Flathubon:
  https://flathub.org/api/v2/appstream/<id>
"""

# source: "flathub" (alapértelmezett), "github-bundle" (Flatpak csomag egy GitHub kiadásból), "system": már a
# rendszerben van, csak be kell kapcsolni (a "switch" script "on" paraméterrel; pl. a KDE Connect nincs a Flathubon),
# vagy "windows": Windows-program (pl. játékindító), amelynek hivatalos telepítőjét ("url", mentve "file" néven) a
# varázsló letölti; a telepítés a varázsló bezárása után következik, egyesével, az .exe kezelőben (sloth-exe --queued)
CATEGORIES = [
    {
        "id": "browser", "icon": "internet-web-browser",
        "apps": [
            {"id": "org.mozilla.firefox", "name": "Firefox"},
            {"id": "com.google.Chrome", "name": "Google Chrome"},
            {"id": "com.brave.Browser", "name": "Brave"},
            {"id": "com.microsoft.Edge", "name": "Microsoft Edge"},
            {"id": "app.zen_browser.zen", "name": "Zen"},
            {"id": "com.vivaldi.Vivaldi", "name": "Vivaldi"},
            {"id": "com.opera.Opera", "name": "Opera"},
            {"id": "io.gitlab.librewolf-community", "name": "LibreWolf"},
            {"id": "org.chromium.Chromium", "name": "Chromium"},
            {"id": "one.ablaze.floorp", "name": "Floorp"},
            {"id": "org.torproject.torbrowser-launcher", "name": "Tor Browser"},
        ],
    },
    {
        "id": "office", "icon": "applications-office",
        "apps": [
            {"id": "org.libreoffice.LibreOffice", "name": "LibreOffice"},
            {"id": "org.onlyoffice.desktopeditors", "name": "ONLYOFFICE"},
            {"id": "com.wps.Office", "name": "WPS Office"},
            {"id": "org.mozilla.Thunderbird", "name": "Thunderbird"},
            {"id": "md.obsidian.Obsidian", "name": "Obsidian"},
            {"id": "net.cozic.joplin_desktop", "name": "Joplin"},
            {"id": "com.bitwarden.desktop", "name": "Bitwarden"},
        ],
    },
    {
        "id": "media", "icon": "applications-multimedia",
        "apps": [
            {"id": "org.videolan.VLC", "name": "VLC"},
            {"id": "org.kde.haruna", "name": "Haruna"},
            {"id": "io.mpv.Mpv", "name": "mpv"},
            {"id": "com.spotify.Client", "name": "Spotify"},
            {"id": "org.kde.elisa", "name": "Elisa"},
            {"id": "com.stremio.Stremio", "name": "Stremio"},
            {"id": "tv.plex.PlexDesktop", "name": "Plex"},
            {"id": "com.github.iwalton3.jellyfin-media-player", "name": "Jellyfin"},
        ],
    },
    {
        "id": "chat", "icon": "kopete", "fallback_icon": "dialog-messages",
        "apps": [
            {"id": "com.discordapp.Discord", "name": "Discord"},
            {"id": "org.telegram.desktop", "name": "Telegram"},
            {"id": "org.signal.Signal", "name": "Signal"},
            {"id": "com.rtosta.zapzap", "name": "ZapZap"},
            {"id": "org.kde.kdeconnect", "name": "KDE Connect",
             "source": "system", "switch": "/usr/libexec/sloth-os/phone-link"},
            {"id": "us.zoom.Zoom", "name": "Zoom"},
            {"id": "com.slack.Slack", "name": "Slack"},
            {"id": "com.github.IsmaelMartinez.teams_for_linux", "name": "Teams for Linux"},
            {"id": "im.riot.Riot", "name": "Element"},
            {"id": "com.viber.Viber", "name": "Viber"},
        ],
    },
    {
        "id": "games", "icon": "applications-games",
        "apps": [
            {"id": "com.valvesoftware.Steam", "name": "Steam"},
            {"id": "com.heroicgameslauncher.hgl", "name": "Heroic"},
            {"id": "org.prismlauncher.PrismLauncher", "name": "Prism Launcher"},
            {"id": "net.lutris.Lutris", "name": "Lutris"},
            {"id": "io.itch.itch", "name": "itch"},
            {"id": "org.libretro.RetroArch", "name": "RetroArch"},
            # Windows-os játékindítók: a hivatalos telepítő, a varázsló után telepítve (az ikonok a gyártóké, NOTICE)
            {"id": "win.battlenet", "name": "Battle.net", "source": "windows", "file": "Battle.net-Setup.exe",
             "url": "https://www.battle.net/download/getInstallerForGame?os=win&gameProgram=BATTLENET_APP&version=Live"},
            {"id": "win.ea", "name": "EA app", "source": "windows", "file": "EAappInstaller.exe",
             "url": "https://origin-a.akamaihd.net/EA-Desktop-Client-Download/installer-releases/EAappInstaller.exe"},
            {"id": "win.ubisoft", "name": "Ubisoft Connect", "source": "windows", "file": "UbisoftConnectInstaller.exe",
             "url": "https://static3.cdn.ubi.com/orbit/launcher_installer/UbisoftConnectInstaller.exe"},
            {"id": "win.epic", "name": "Epic Games", "source": "windows", "file": "EpicGamesLauncherInstaller.msi",
             "url": "https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/"
                    "EpicGamesLauncherInstaller.msi"},
            {"id": "win.gog", "name": "GOG Galaxy", "source": "windows", "file": "GOG_Galaxy_2.0.exe",
             "url": "https://webinstallers.gog-statics.com/download/GOG_Galaxy_2.0.exe"},
            {"id": "win.rockstar", "name": "Rockstar Games", "source": "windows", "file": "Rockstar-Games-Launcher.exe",
             "url": "https://gamedownloads.rockstargames.com/public/installer/Rockstar-Games-Launcher.exe"},
        ],
    },
    {
        "id": "creative", "icon": "applications-graphics",
        "apps": [
            {"id": "ai.storyteller.artcraft-launcher", "name": "ArtCraft",
             "source": "github-bundle", "repo": "storytold/craft-launcher", "asset_suffix": "-linux-x86_64.flatpak"},
            {"id": "org.gimp.GIMP", "name": "GIMP"},
            {"id": "org.kde.krita", "name": "Krita"},
            {"id": "org.inkscape.Inkscape", "name": "Inkscape"},
            {"id": "org.kde.kdenlive", "name": "Kdenlive"},
            {"id": "com.obsproject.Studio", "name": "OBS Studio"},
            {"id": "org.blender.Blender", "name": "Blender"},
            {"id": "org.audacityteam.Audacity", "name": "Audacity"},
            {"id": "org.darktable.Darktable", "name": "darktable"},
            {"id": "org.shotcut.Shotcut", "name": "Shotcut"},
        ],
    },
]

ICON_DIR = "/usr/share/sloth-os/welcome/icons"


def find_app(app_id):
    for cat in CATEGORIES:
        for app in cat["apps"]:
            if app["id"] == app_id:
                return app
    return None
