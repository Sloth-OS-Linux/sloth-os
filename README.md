# Sloth OS 🦥

A Linux desktop for everyday use and gaming that an average user can use just like Windows: **no terminal required**.

[![Support Sloth OS on Ko-fi](https://img.shields.io/badge/Buy%20us%20a%20beer-Ko--fi-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/slothos)

- **Base:** Universal Blue `kinoite-main` / `kinoite-nvidia` (Fedora Atomic + KDE Plasma)
- **Updates:** atomic, in the background; if something breaks, roll back to the previous version from the boot menu
- **Apps:** Flatpak (Flathub); nothing is preinstalled, the user picks the apps in the Sloth Welcome wizard
- **Build:** [BlueBuild](https://blue-build.org) + GitHub Actions; a new image is built every day and after every
  commit

**Download and user guides: [sloth-os-linux.github.io](https://sloth-os-linux.github.io/)** (website source:
[Sloth-OS-Linux/sloth-os-linux.github.io](https://github.com/Sloth-OS-Linux/sloth-os-linux.github.io)). The
installer ISO is hosted on [SourceForge](https://sourceforge.net/projects/sloth-os/files/).

**Current release: Sloth OS 1.2.1** (October 29, 2026). Machines already running Sloth OS get it as a normal
update. Download: [sloth-os-1.2.1-x86_64.iso](https://sourceforge.net/projects/sloth-os/files/1.2.1/sloth-os-1.2.1-x86_64.iso/download) (5.2 GB, also as a
[torrent](https://sourceforge.net/projects/sloth-os/files/1.2.1/sloth-os-1.2.1-x86_64.iso.torrent/download)), SHA-256 `17e24d611fda24bba8fbf7c247f282c6cff1f2be974462e57ecd32a14c84ac14`. What changed:
[release notes](#release-notes) below (also in [docs/releases/1.2.1.md](docs/releases/1.2.1.md)).

## What Sloth OS can do

**Feels familiar from the first minute.** Pick a taskbar layout that looks like Windows 10, Windows 11, a Mac or
Ubuntu, and a color scheme, in the welcome wizard or any time later. Nothing is preinstalled: the Sloth Welcome
wizard lets you choose your apps (browsers, Steam, Discord, office, media and more) and installs them for you, and
only what you chose goes on the taskbar. Every text is available in 50 languages.

**One place for settings: Sloth Center.** Updates, disks and what uses the space, network folders (NAS), file
backup and restore, displays (refresh rate, VRR, HDR), sound and microphone test, Bluetooth, a Wi-Fi check in plain
language, controllers, programs that start at sign-in, app permissions, a security overview and system health, a
Feedback page and offline Help for the most common problems. A short guided tour shows where everything is.

**Games that just work.** Steam, Proton, GameMode and gamescope are ready to go, with an FPS and temperature display
per game, controller support, and the NVIDIA driver set up by itself on computers with an NVIDIA card. "Will it run?"
tells how well a game runs before you buy it, and a Steam game moves to another drive without downloading it again.

**Windows programs without fuss.** Double-click an `.exe`, `.msi` or a disc image and it installs or runs, without
Steam and without settings. If a program does not start, Sloth OS finds a setting that works by itself and
remembers it ([how it works](#windows-programs-that-just-start)).

**Safe, quiet updates.** The system updates itself in the background as one piece and switches over at the next
restart. An update downloads only the parts that changed (a typical one is a few hundred MB), and it never asks
for a restart in your quiet hours. If something goes wrong, the previous version is one click away. Images are signed, and your home folder
keeps earlier versions of your files so you can restore one or find a deleted file.

**An installer that explains itself.** Install on the whole disk or next to Windows (Windows is never touched),
choose what happens with other disks, and encrypt the disk if you like. No terminal, no text scrolling by: just a
progress bar and plain sentences.

## Release notes

<details open>
<summary><b>What's new in 1.2.1</b> (October 29, 2026)</summary>

**Roblox:** Sloth Welcome offers **Sober** for Roblox games (a community app made for Linux; Roblox blocks its
Windows version on Linux) and the official **Roblox Studio**, installed after the wizard like the other Windows
launchers, with a working login. "Will it run?" answers Roblox with Sober.

**Windows programs:** logging in through the browser works (the browser's link back to the program now reaches it),
and the Microsoft Edge WebView2 component that some installers bring is no longer mistaken for the program.

Every new text is in all 50 languages.

</details>

<details>
<summary><b>What's new in 1.2</b> (October 28, 2026)</summary>

**Much smaller updates.** An update now downloads only the parts of the system that changed: on a real machine a
typical update was about 300 MB instead of 2–4 GB, and the installer ISO shrank from 7.0 GB to 5.2 GB. Coming from
1.1, the first update downloads the whole system once (about 4.5 GB); after that, updates are small.

**Sloth Center**

- **Help:** the most common problems answered offline, in every language, each with a button to the page that
  fixes it.
- **"Will it run?"** on the Games page: about 20 000 games with how well they run, from other players' reports, the
  anti-cheat and the source of every answer; when the makers block Linux, it says so and whom to ask.
- **Move a Steam game to another drive** without downloading it again (the game, its saves and Steam's library list).
- **Network folders** (Disks page): a NAS or a shared folder in the file manager's side panel, found by itself or
  typed as `\\NAS\Photos`; it says which setting to turn on when a NAS shares nothing.
- **Quiet hours** for restart reminders, and **the hour the automatic update downloads**.
- **Display and sound profiles:** save "Desk", "TV" or "Headset" and switch with one click.
- **Settings to a file and back:** the look, the profiles, the quiet hours and the apps, which Sloth Welcome installs
  again on a new machine.
- **Clean up** shows each item and its size first, and deletes only what you tick.

**Installer and Windows programs**

- The installer checks the computer on its first page (UEFI mode, memory, a laptop on battery), and its last steps
  say what is happening instead of standing at 80%.
- WinUI 3 / .NET MAUI programs, which do not run on Linux yet, are recognized and explained.
- In live mode (from the USB stick) Windows programs start sooner and use less memory.

Every new text is in all 50 languages.

</details>

<details>
<summary><b>What's new in 1.1</b> (October 27, 2026)</summary>

The biggest update since 1.0: Sloth Center learned most of what people look for in Windows' Settings (displays,
sound, Bluetooth, Wi-Fi, startup programs, app permissions, appearance), and Windows programs install and start more
reliably.

**Updates that finish.** A system update could stop halfway and never finish (the system switched off a part of the
disk in the middle of it). This is fixed and was checked with a full 2.3 GB update on a real machine. The Updates page
also shows how big the waiting update is, and on a mobile or other metered connection it asks before downloading.

**Sloth Center**

- **A guided tour that shows where things are:** the first-run guide darkens the window and lights up the pages it
  talks about, one step at a time.
- **Appearance:** change the taskbar layout and the colors any time, the same ones as in the welcome wizard. New
  layout: **Ubuntu-like** (a top bar with the date and time in the middle, a floating dock on the left, the app grid
  sliding out from it), also in the wizard.
- **Displays:** each monitor by its own name, with its refresh rate and the highest one it can do. If it runs below
  that (a 144 Hz monitor at 60 or 100 Hz), one button switches it. Variable refresh rate (FreeSync, G-Sync) and HDR
  switches where the monitor supports them. After a change it asks whether to keep it and goes back by itself after
  15 seconds.
- **Sound:** choose the speakers or headphones and the microphone, play a test sound, and test the microphone (it
  records a few seconds, plays it back, and tells you if it heard nothing).
- **Bluetooth:** whether the computer has it, whether it is on (with a button to turn it on), and the connected
  devices with their battery.
- **Wi-Fi check:** step by step in plain language (adapter, switched on, connected, signal, internet, a hotel or train
  network that wants a sign-in), with a button where one helps.
- **Programs that start when you sign in:** see them, turn them off, or add one (for example Steam).
- **App permissions:** which apps can use the camera, the microphone and the location.
- **File backup:** restore a file or find deleted ones without knowing the right-click menu, and check that the
  backup can really be read back.
- **FPS display while playing** now also shows the CPU and GPU temperatures and the memory.

**Installing and Windows programs**

- **More than one screen:** the installer asks which one is the main screen, and the installed system keeps it.
- **Your taskbar, your choice:** at the end of the welcome wizard you pick which of the installed apps go on the
  taskbar.
- **Other disks:** "Use it" now lets you pick the Linux partitions one by one, also on a disk with Windows (Windows
  partitions are never touched).
- **Disc images:** double-click an `.iso` and it opens like a disc on Windows; if it has an installer, Sloth OS offers
  to run it. It is ejected again when you sign out.
- **Installers fix themselves:** if a Windows installer crashes because something is missing, it is tried again with
  the fix, and what worked is remembered (and shared, if sharing is on).
- **Installers that open the program at the end** (like IrfanView's) no longer keep the install screen waiting until
  you close the program, also when reinstalling.
- **Sloth OS sees which Windows programs are running:** starting one that is already open says so instead of opening
  it twice, and a launcher that hands over to its client (like Battle.net) is followed correctly.
- Closed Windows programs are no longer started again by themselves, and installers like 7-Zip's are recognized
  correctly.

**Smaller fixes**

- Cloud storage in Sloth Center: the connect buttons work again (before, both spinners turned and nothing happened).
- A background sign-in check no longer reports an error at every start.
- The terminal's system information (fastfetch) shows the Sloth OS logo.

Every new text is in all 50 languages.

</details>

<details>
<summary><b>1.0.4</b> (October 26, 2026)</summary>

- **More than one disk:** the installer asks what to do with each other disk: leave it alone (the default), use it
  with its files, or erase it for programs and games. A disk with Windows on it is never changed.
- **Choose the drive for Windows programs:** with more than one drive, the `.exe` handler asks where a new program
  goes and shows the free space on each.
- **See what uses the space:** Sloth Center → Disks shows your files, games, Windows programs, apps, temporary files
  and the system separately, and *Clean up* now also removes temporary system files and cached update data.
- **System status at a glance:** network connection and router latency, a security overview (Secure Boot, disk
  encryption, signed updates), and a warning with a backup button if a drive reports that it may fail.
- **Clearer updates:** the progress bar moves part by part during a system update, and an interrupted update no
  longer leaves Sloth Center spinning forever.
- New hanging sloth artwork, and every text in all 50 languages.

If you tried installing with an earlier 1.0.2 ISO and ran into problems, we are sorry: that installer issue is fixed.

</details>

## System requirements

| | Minimum | Recommended for games |
|---|---|---|
| Computer | 64-bit PC (x86_64) that starts in **UEFI** mode (almost every PC from 2013 or later) | |
| Processor | 2 cores | 4 cores or more |
| Memory | 4 GB | 16 GB |
| Disk space | 64 GB | 256 GB SSD or more |
| Graphics | Any Intel, AMD or NVIDIA graphics | AMD Radeon RX 400 series or newer, Intel Arc / Iris Xe, NVIDIA GeForce GTX 16 / RTX 20 series or newer |
| USB stick | 8 GB or more for the installer | |

Not supported yet: BIOS-only PCs, ARM computers, and NVIDIA cards older than the GTX 16 series (the NVIDIA image uses
NVIDIA's open kernel driver). NVIDIA computers have been tried with Secure Boot turned off. Installing next to Windows needs at least
64 GB of free space for Sloth OS. Download and step-by-step guide:
[sloth-os-linux.github.io/download.html](https://sloth-os-linux.github.io/download.html).

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
   ([Sloth-OS-Linux/sloth-os-knowledge](https://github.com/Sloth-OS-Linux/sloth-os-knowledge)): settings
   derived from the open [ProtonDB](https://www.protondb.com) data (ODbL), plus what worked on other Sloth OS
   machines. That setting is the first attempt, so programs start on the first try.

### Where programs live

Every Windows program gets its own visible folder, `~/Applications/<program>/`, with a "Program files" link to
the installed files; its Windows environment and Sloth's data about it sit next to it (`windows/`, `.sloth/`).
After installing, the program's real name and the file that starts it are detected from the Windows registry
and the installer's shortcuts; if that is not certain, the user picks or browses for the file. If the computer has more than one drive,
the user picks the drive when installing (other internal drives with a Linux file system are offered by themselves;
USB sticks are not). In Sloth Center →
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
rpm-ostree rebase ostree-unverified-registry:ghcr.io/sloth-os-linux/sloth-os:latest
systemctl reboot

# Step 2: rebase to the signed image
rpm-ostree rebase ostree-image-signed:docker://ghcr.io/sloth-os-linux/sloth-os:latest
systemctl reboot
```

On NVIDIA machines, do the same with `sloth-os-nvidia`.

> This is the developer path. End users install from the installer ISO and never see commands like these.

## Installer ISO

Sloth OS has its own live system and installer (no Anaconda): see [`iso/README.md`](iso/README.md). Build it with
`tools/build-iso.sh` (Linux) or `tools/build-iso.ps1` (Windows).
On Windows, `tools/write-usb.ps1` writes the newest ISO from `out/` to a USB stick and verifies it
(it asks for administrator approval; the stick is erased, only USB disks up to 256 GB are accepted).

## License

The code is licensed under the [Apache License 2.0](LICENSE). The Sloth OS artwork (logo, wallpapers, boot
animation) is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The app icons in the
Sloth Welcome belong to their respective owners. Details: [`NOTICE`](NOTICE).

## Support

Sloth OS is free and made in spare time. If you like it, you can support its development with a beer on
[Ko-fi](https://ko-fi.com/slothos). Sending feedback from Sloth Center → Feedback helps just as much.
