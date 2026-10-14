# Our own tools

This is where Sloth OS's own graphical tools go (see docs/ROADMAP.md, phase 3).

Recommended technology: **Python + Qt (PySide6) / QML**, so they fit natively into KDE Plasma.
The GUI tools themselves live in `files/system/usr/lib/sloth-os/<tool>/`, because the build
only sees the `files/` folder. Their launchers are in `files/system/usr/bin/` and their menu
entries in `files/system/usr/share/applications/`. The runtime packages are in `recipes/tools.yml`.

This folder holds developer helpers that are not part of the image (e.g. `branding/`).

## Translations

The Sloth Welcome texts live in `files/system/usr/lib/sloth-os/sloth-welcome/sloth_welcome/translations/`,
one JSON file per language (`hu.json` is the source and is always complete). To add a language, copy
`hu.json` to e.g. `fr.json`, set `_language` to the language's own name (`Français`) and translate the values;
keep the `{placeholders}` as they are. Missing keys fall back to English, then Hungarian.

Check them with `python tools/check_translations.py` (reports missing keys and mismatched placeholders).
