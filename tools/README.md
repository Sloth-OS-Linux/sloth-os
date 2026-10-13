# Saját eszközök

Ide kerülnek a Sloth OS saját grafikus eszközei (lásd docs/ROADMAP.md, 3. fázis).

Javasolt technológia: **Python + Qt (PySide6) / QML**, hogy natívan illeszkedjenek a KDE Plasmához.
Minden eszköz a saját almappájába kerül.

FONTOS: a build jelenleg még nem másolja be ezt a mappát az image-be. Az első eszköznél
fel kell venni egy `files` modul-bejegyzést (vagy egy scriptet) a `recipes/branding.yml`-be,
ami a `tools/<eszköz>` tartalmát a megfelelő helyre (pl. `/usr/share/sloth-os/`, `/usr/bin/`) teszi.
