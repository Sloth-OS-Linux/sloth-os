"""A varázslóban felkínált appok. Alapból semmi nincs kiválasztva: a felhasználó dönt.

Minden app Flatpak a Flathubról, kivéve ahol `source` mást mond. Az ikonok
helyben vannak (/usr/share/sloth-os/welcome/icons/<id>.png), így a lista
internet nélkül is rendesen néz ki.

Új app felvétele előtt ellenőrizd, hogy létezik-e a Flathubon:
  https://flathub.org/api/v2/appstream/<id>
"""

# source: "flathub" (alapértelmezett) vagy "github-bundle" (Flatpak csomag egy GitHub kiadásból)
CATEGORIES = [
    {
        "id": "browser", "name": "Böngésző", "icon": "internet-web-browser",
        "hint": "Ezzel netezel. Böngésző nélkül nem tudsz weboldalakat megnyitni.",
        "apps": [
            {"id": "org.mozilla.firefox", "name": "Firefox", "summary": "Gyors, adatvédelemre figyelő, nyílt forrású"},
            {"id": "com.google.Chrome", "name": "Google Chrome", "summary": "A Google böngészője, Google-fiókkal szinkronizál"},
            {"id": "com.brave.Browser", "name": "Brave", "summary": "Beépített reklámblokkolóval"},
            {"id": "com.microsoft.Edge", "name": "Microsoft Edge", "summary": "A Windowsról ismert böngésző"},
            {"id": "app.zen_browser.zen", "name": "Zen", "summary": "Letisztult, Firefox-alapú"},
            {"id": "com.vivaldi.Vivaldi", "name": "Vivaldi", "summary": "Rengeteg testreszabási lehetőség"},
            {"id": "com.opera.Opera", "name": "Opera", "summary": "Beépített VPN-nel és csevegőkkel"},
            {"id": "io.gitlab.librewolf-community", "name": "LibreWolf", "summary": "A Firefox még privátabb változata"},
            {"id": "org.chromium.Chromium", "name": "Chromium", "summary": "A Chrome nyílt forrású alapja"},
        ],
    },
    {
        "id": "office", "name": "Irodai programok", "icon": "applications-office",
        "hint": "Szövegszerkesztő, táblázatkezelő, prezentáció. Megnyitja a Word és Excel fájlokat is.",
        "apps": [
            {"id": "org.libreoffice.LibreOffice", "name": "LibreOffice", "summary": "Teljes, ingyenes irodai csomag"},
            {"id": "org.onlyoffice.desktopeditors", "name": "ONLYOFFICE", "summary": "A Microsoft Office-hoz hasonló kinézet"},
            {"id": "com.wps.Office", "name": "WPS Office", "summary": "Office-szerű felület, sok sablonnal"},
        ],
    },
    {
        "id": "media", "name": "Zene és videó", "icon": "applications-multimedia",
        "hint": "Filmek, videók és zene lejátszása.",
        "apps": [
            {"id": "org.videolan.VLC", "name": "VLC", "summary": "Mindent lejátszik"},
            {"id": "org.kde.haruna", "name": "Haruna", "summary": "Egyszerű videólejátszó, illik a rendszerhez"},
            {"id": "io.mpv.Mpv", "name": "mpv", "summary": "Pehelykönnyű videólejátszó"},
            {"id": "com.spotify.Client", "name": "Spotify", "summary": "Zene streamelés"},
        ],
    },
    {
        "id": "chat", "name": "Csevegés", "icon": "internet-chat",
        "hint": "Üzenetek, hang- és videóhívások.",
        "apps": [
            {"id": "com.discordapp.Discord", "name": "Discord", "summary": "Csevegés játék közben és közösségek"},
            {"id": "org.telegram.desktop", "name": "Telegram", "summary": "Gyors üzenetküldő"},
            {"id": "org.signal.Signal", "name": "Signal", "summary": "Titkosított üzenetek"},
            {"id": "com.rtosta.zapzap", "name": "ZapZap", "summary": "WhatsApp a számítógépen"},
        ],
    },
    {
        "id": "games", "name": "Játékok", "icon": "applications-games",
        "hint": "A Steam már telepítve van. Ezekkel más boltok játékai is mennek.",
        "apps": [
            {"id": "com.heroicgameslauncher.hgl", "name": "Heroic", "summary": "Epic Games, GOG és Amazon játékok"},
            {"id": "org.prismlauncher.PrismLauncher", "name": "Prism Launcher", "summary": "Minecraft"},
            {"id": "net.lutris.Lutris", "name": "Lutris", "summary": "Sok más játékbolt és régi játékok"},
        ],
    },
    {
        "id": "creative", "name": "Alkotás", "icon": "applications-graphics",
        "hint": "Képszerkesztés, rajzolás, videóvágás, felvétel.",
        "apps": [
            {"id": "ai.storyteller.artcraft-launcher", "name": "ArtCraft", "summary": "A Craft appok (PhotoCraft, FilmCraft…) egy helyen",
             "source": "github-bundle", "repo": "storytold/craft-launcher", "asset_suffix": "-linux-x86_64.flatpak"},
            {"id": "org.gimp.GIMP", "name": "GIMP", "summary": "Fotószerkesztés"},
            {"id": "org.kde.krita", "name": "Krita", "summary": "Digitális rajzolás és festés"},
            {"id": "org.inkscape.Inkscape", "name": "Inkscape", "summary": "Vektorgrafika, logók"},
            {"id": "org.kde.kdenlive", "name": "Kdenlive", "summary": "Videóvágás"},
            {"id": "com.obsproject.Studio", "name": "OBS Studio", "summary": "Képernyőfelvétel és streamelés"},
            {"id": "org.blender.Blender", "name": "Blender", "summary": "3D modellezés és animáció"},
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
