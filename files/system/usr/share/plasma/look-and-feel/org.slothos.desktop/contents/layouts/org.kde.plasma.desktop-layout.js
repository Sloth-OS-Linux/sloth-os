// Sloth OS alapértelmezett asztal: Windows-szerű tálca alul.
// Csak új felhasználónál fut (amikor még nincs saját panel-beállítás).

const panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.5 / 2);
panel.floating = false;

// Start menü a Sloth OS logóval
const kickoff = panel.addWidget("org.kde.plasma.kickoff");
kickoff.currentConfigGroup = ["General"];
kickoff.writeConfig("icon", "sloth-os");

// Rögzített appok + futó ablakok (csak ikonok, mint a Windowsban).
// A böngészőt és a Steamet a Sloth Üdvözlő tűzi ki, ha a felhasználó telepítette őket.
const tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "applications:org.kde.dolphin.desktop",
    "applications:org.kde.discover.desktop",
].join(","));

panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");
panel.addWidget("org.kde.plasma.showdesktop");

// Asztal: az alapértelmezett Sloth OS háttérkép (a többi a Háttérkép beállításoknál választható)
for (const desktop of desktops()) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/wallpapers/SlothOS-metallic-sloth-over-silver-waves/");
}
