# Our own tools

This is where Sloth OS's own graphical tools go (see docs/ROADMAP.md, phase 3).

Recommended technology: **Python + Qt (PySide6) / QML**, so they fit natively into KDE Plasma.
Each tool goes into its own subfolder.

IMPORTANT: the build does not copy this folder into the image yet. With the first tool,
add a `files` module entry (or a script) to `recipes/branding.yml` that puts the contents
of `tools/<tool>` in the right place (e.g. `/usr/share/sloth-os/`, `/usr/bin/`).
