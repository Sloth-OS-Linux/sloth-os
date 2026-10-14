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

# source: "flathub" (alapértelmezett) vagy "github-bundle" (Flatpak csomag egy GitHub kiadásból)
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
        ],
    },
    {
        "id": "office", "icon": "applications-office",
        "apps": [
            {"id": "org.libreoffice.LibreOffice", "name": "LibreOffice"},
            {"id": "org.onlyoffice.desktopeditors", "name": "ONLYOFFICE"},
            {"id": "com.wps.Office", "name": "WPS Office"},
        ],
    },
    {
        "id": "media", "icon": "applications-multimedia",
        "apps": [
            {"id": "org.videolan.VLC", "name": "VLC"},
            {"id": "org.kde.haruna", "name": "Haruna"},
            {"id": "io.mpv.Mpv", "name": "mpv"},
            {"id": "com.spotify.Client", "name": "Spotify"},
        ],
    },
    {
        "id": "chat", "icon": "kopete", "fallback_icon": "dialog-messages",
        "apps": [
            {"id": "com.discordapp.Discord", "name": "Discord"},
            {"id": "org.telegram.desktop", "name": "Telegram"},
            {"id": "org.signal.Signal", "name": "Signal"},
            {"id": "com.rtosta.zapzap", "name": "ZapZap"},
        ],
    },
    {
        "id": "games", "icon": "applications-games",
        "apps": [
            {"id": "com.heroicgameslauncher.hgl", "name": "Heroic"},
            {"id": "org.prismlauncher.PrismLauncher", "name": "Prism Launcher"},
            {"id": "net.lutris.Lutris", "name": "Lutris"},
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
