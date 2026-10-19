# Sloth OS 🦥

A Linux desktop for everyday use and gaming that an average user can use just like Windows: **no terminal required**.

- **Base:** Universal Blue `kinoite-main` / `kinoite-nvidia` (Fedora Atomic + KDE Plasma)
- **Updates:** atomic, in the background; if something breaks, roll back to the previous version from the boot menu
- **Apps:** Flatpak (Flathub); nothing is preinstalled, the user picks the apps in the Sloth Welcome wizard
- **Build:** [BlueBuild](https://blue-build.org) + GitHub Actions; a new image is built after every commit (daily
  builds will be switched back on once the repository is public)

Website and user guides: [`website/`](website/README.md) (published with GitHub Pages once the repository is
public).

## Windows programs that just start

Double-click a Windows `.exe` or `.msi` and it installs or runs, without Steam and without the user ever
seeing the words "Wine", "Proton" or "prefix". Under the hood it runs on Proton via
[umu-launcher](https://github.com/Open-Wine-Components/umu-launcher) (with the system Wine as an offline
fallback). There is no single Proton setting that works for everything, so the `.exe` handler
(`files/system/usr/lib/sloth-os/sloth-exe/`) finds the one that works for each program by itself. The user
only sees "Starting…":

1. **Recognition.** The program's product name is read from the `.exe` and looked up in the umu database
   and, if needed, the Steam store. A recognized program gets the community fixes of
   [umu-protonfixes](https://github.com/Open-Wine-Components/umu-protonfixes) and Proton's own
   per-game fixes.
2. **Recipes** for known launchers (e.g. Battle.net).
3. **Diagnosis.** The runner's output is always logged in the background. If a program exits right away,
   known errors are fixed directly: a missing DLL installs the right component (Visual C++, DirectX parts,
   .NET…), a Vulkan failure switches to WineD3D, and so on.
4. **Self-healing.** Otherwise other settings are tried one after another (without fsync, WineD3D,
   GE-Proton, an older Proton). Before switching Proton versions, a snapshot of the program's folder is
   taken (a Btrfs reflink copy: instant and nearly free), so a failed attempt never breaks anything. What
   works is remembered for that program.
5. **Rollback after updates.** If a new Proton version breaks a program that used to work, that program
   stays on the last working version.
6. **Shared knowledge.** Every machine downloads a public file of settings known to work
   ([bathorizsolt/sloth-os-knowledge](https://github.com/bathorizsolt/sloth-os-knowledge)): settings
   derived from the open [ProtonDB](https://www.protondb.com) data (ODbL), plus what worked on other Sloth OS
   machines. That setting is the first attempt, so programs start on the first try.

### Where programs live

Every Windows program gets its own visible folder, `~/Applications/<program>/`, with a "Program files" link to
the installed files; its Windows environment and Sloth's data about it sit next to it (`windows/`, `.sloth/`).
After installing, the program's real name and the file that starts it are detected from the Windows registry
and the installer's shortcuts; if that is not certain, the user picks or browses for the file. In Sloth Center →
Windows programs each program can be started, opened in the file manager, repaired, reinstalled, moved (for
example to another drive) or removed. Programs installed elsewhere (added to Steam by hand, in Lutris, in Bottles, or
in a plain `~/.wine`) can be taken over without reinstalling, either started by the original app as before or as an
independent copy; the original files are never changed. The shared
code is in `files/system/usr/lib/sloth-os/common/sloth_common/apps/` (tests: `tools/tests/test_apps.py`).

The same handler opens Linux packages: an AppImage is installed into `~/Applications` with a Start menu entry, a
`.deb` or `.rpm` goes into a hidden Ubuntu or Fedora container whose apps appear in the Start menu like native ones
(with a "Search in Discover" alternative), and Mac files get a clear explanation instead of an error.

### Privacy

Sharing is **opt-in**: the Sloth Welcome wizard asks, and it can be changed any time in Sloth Center →
Windows programs. If it is on, the machine anonymously reports which setting worked (or did not) for a
program. A report contains only the setting, the GPU manufacturer (AMD, NVIDIA, Intel), a hash of the
program's name computed on the machine (the name itself is never sent and cannot be recovered), and a random
machine ID. Nothing else leaves the computer: no user name, no files, no program names, no usage times.
Reports are queued and sent in the background. Downloading the shared knowledge reveals nothing either: it is
the same static file for everyone. The service only accepts allowlisted settings and publishes a setting
only after it worked on several different machines. Details: [`services/knowledge/`](services/knowledge/).

## Layout

```
recipes/
  recipe.yml          # AMD / Intel image
  recipe-nvidia.yml   # NVIDIA image
  branding.yml        # name, logos, default settings
  gaming.yml          # gamescope, mangohud, gamemode...
  apps.yml            # Flatpak setup (Flathub, no preinstalled apps)
files/
  scripts/            # scripts run during the build (e.g. branding.sh)
  system/             # everything here is copied into the root of the final system
tools/                # developer helpers (ISO build, translation checks…)
iso/                  # live system and installer of the install ISO
services/knowledge/   # shared-knowledge service (Cloudflare Worker), not part of the image
docs/ROADMAP.md       # the plan
```

## First-time setup (once)

1. Create a **public** GitHub repository named `sloth-os` and push this folder to it.
2. Generate a signing key in the repository folder (leave the password empty):
   ```
   cosign generate-key-pair
   ```
3. On GitHub: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `SIGNING_SECRET`
   - Value: the full contents of `cosign.key`
4. Commit `cosign.pub`. `cosign.key` must **never** be committed (`.gitignore` excludes it).
5. After pushing, the build starts under the **Actions** tab. When it finishes, the `sloth-os` and `sloth-os-nvidia` images appear under **Packages**.

## Trying it out (in a VM or on a test machine)

Install plain **Fedora Kinoite**, then:

```
# Step 1: rebase to the image (without signature verification yet)
rpm-ostree rebase ostree-unverified-registry:ghcr.io/bathorizsolt/sloth-os:latest
systemctl reboot

# Step 2: rebase to the signed image
rpm-ostree rebase ostree-image-signed:docker://ghcr.io/bathorizsolt/sloth-os:latest
systemctl reboot
```

On NVIDIA machines, do the same with `sloth-os-nvidia`.

> This is the developer path. End users will later get their own installer ISO and will never see commands like these.

## Installer ISO

Sloth OS has its own live system and installer (no Anaconda): see [`iso/README.md`](iso/README.md). Build it with
`tools/build-iso.sh` (Linux) or `tools/build-iso.ps1` (Windows).

## License

The code is licensed under the [Apache License 2.0](LICENSE). The Sloth OS artwork (logo, wallpapers, boot
animation) is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The app icons in the
Sloth Welcome belong to their respective owners. Details: [`NOTICE`](NOTICE).
