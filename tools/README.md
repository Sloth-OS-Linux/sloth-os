# Our own tools

This is where Sloth OS's own graphical tools go (see docs/ROADMAP.md, phase 3).

Recommended technology: **Python + Qt (PySide6) / QML**, so they fit natively into KDE Plasma.
The GUI tools themselves live in `files/system/usr/lib/sloth-os/<tool>/`, because the build
only sees the `files/` folder. Their launchers are in `files/system/usr/bin/` and their menu
entries in `files/system/usr/share/applications/`. The runtime packages are in `recipes/tools.yml`.

This folder holds developer helpers that are not part of the image (e.g. `branding/`).
