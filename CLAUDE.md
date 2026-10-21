# Sloth OS – guide for Claude Code

## What this is
A desktop distribution built with BlueBuild on the Universal Blue `kinoite-main` / `kinoite-nvidia` images (Fedora
Atomic). Goal: a Windows alternative for average users, with strong gaming support.
**Everything in the repository is English**: code, comments, docstrings, log messages, documentation (including
`docs/ROADMAP.md`) and commit messages. The user interface is translated into 50 languages (Hungarian is one of them);
English is the source language of every translation.

## Principles
- **The user never needs a terminal.** Konsole stays available, but anything someone would do in a terminal (any
  setting, however many) must also work from a GUI. If something only works from the command line, that is a bug.
  This applies to developer tasks too (repository, keys, build, testing). The coverage list: `docs/ROADMAP.md`, phase 3.
- **No terminal during processes either.** Installing, updating, loading: a progress indicator and a status text in
  plain language (e.g. "Installing Steam… 45%"), never raw command-line output. At boot there is no GRUB menu (only
  after a failed start) and no text output, only the Plymouth animation.
- **Not Bazzite.** Do not use a Bazzite image or Bazzite-specific tools (ujust recipes, bazzite-* packages) as a base.
- **Proton/Wine stay invisible.** The user should not see the words "Wine", "prefix" or "Proton version" unless they
  explicitly ask for them.
- **`ID=fedora` stays** in `/usr/lib/os-release`; only the displayed names change (see `files/scripts/branding.sh`).
- **User apps as Flatpaks**; RPMs only for system-level things (`recipes/gaming.yml` etc.).
  Nothing is preinstalled, not even Steam: the user picks everything in Sloth Welcome
  (`files/system/usr/lib/sloth-os/sloth-welcome/sloth_welcome/catalog.py`). Nothing is selected by default, and only
  what the user installed goes on the taskbar.
- **Windows programs run without Steam too** (.exe handler): umu-launcher + Proton, downloaded in advance in the
  background; the system Wine (`wine-core`) is the fallback, so an .exe starts even without internet.
- Every change goes through the recipes and the `files/` folder. Nothing is set by hand on a running system.

## Layout
- `recipes/recipe.yml`, `recipes/recipe-nvidia.yml`: the two images; they pull in the shared modules with `from-file`.
- `recipes/branding.yml`, `gaming.yml`, `apps.yml`, `tools.yml`: module lists by topic.
- `files/system/`: copied into the root of the finished system.
- `files/scripts/`: scripts run during the build (`type: script` module).
- `files/system/usr/lib/sloth-os/<tool>/`: our own GUI tools (Python + PySide6/QML); `tools/`: developer helpers (not
  in the image).
- `files/system/usr/lib/sloth-os/common/sloth_common/`: shared parts of the tools. Translations: per tool,
  `translations/<language>.json`, with English as the source. Most tools use dotted keys (`welcome.title`); in Sloth
  Center the English sentence itself is the key (`tr("…")`, `L.t("…")`). Checks: `tools/check_translations.py` and
  `tools/extract_center_strings.py --all`. Do not edit the start menu entries (`*.desktop`) by hand:
  `tools/gen_desktop_entries.py` writes them from the translations.
- `iso/`: the live system of the installer ISO and our own Sloth OS installer (only on the ISO, not in the installed
  system). Build: `tools/build-iso.sh` (Linux) or `tools/build-iso.ps1` (Windows).
- `docs/ROADMAP.md`: the plan. Tick off a task when it is done.

## Releases and hosting
- GitHub: `Sloth-OS-Linux/sloth-os` (public); images `ghcr.io/sloth-os-linux/sloth-os(-nvidia)` (lowercase, required
  by ghcr). Website: `Sloth-OS-Linux/sloth-os-linux.github.io` (`docs/` folder), https://sloth-os-linux.github.io/.
- The installer ISO is on SourceForge (https://sourceforge.net/projects/sloth-os/files/).

## Useful to know
- BlueBuild documentation and modules: https://blue-build.org
- Recipe schema: https://schema.blue-build.org/recipe-v1.json
- Local build (if the bluebuild CLI is installed): `bluebuild build recipes/recipe.yml`
- CI runs in `.github/workflows/build.yml` (daily and on every push); it builds both recipes.
- Before adding a new dnf package, check that it exists in the Fedora repositories for the current version.
