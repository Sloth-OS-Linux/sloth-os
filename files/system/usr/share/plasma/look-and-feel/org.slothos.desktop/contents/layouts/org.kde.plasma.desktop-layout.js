// Sloth OS default desktop: a Windows-like taskbar at the bottom.
// It only runs for a new user (when there is no panel setting of their own yet).

const panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.5 / 2);
panel.floating = false;

// Start menu with the Sloth OS logo
const kickoff = panel.addWidget("org.kde.plasma.kickoff");
kickoff.currentConfigGroup = ["General"];
kickoff.writeConfig("icon", "sloth-os");

// Pinned apps + running windows (icons only, as in Windows).
// Sloth Welcome pins the browser and Steam if the user installed them.
// Sloth Center is out by default: every setting and the updates can be reached from it.
const tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "applications:org.kde.dolphin.desktop",
    "applications:org.kde.discover.desktop",
    "applications:org.slothos.center.desktop",
].join(","));

panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");
panel.addWidget("org.kde.plasma.showdesktop");

// Desktop: the default Sloth OS wallpaper (the others can be chosen in the Wallpaper settings)
for (const desktop of desktops()) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/wallpapers/SlothOS-metallic-sloth-over-silver-waves/");
}
