# Sloth OS – plan

Principle: **if the user has to open a terminal, that is our fault.** Konsole stays, but everything that can be done
from a terminal must also work from a GUI.

## Where we are

### Sloth OS 1.0.2 (2026-10-22)
The current 1.0.2 ISO is published on SourceForge and is working in current testing. Sorry to anyone who ran
into trouble installing with the earlier 1.0.2 ISO: the installer issue has been fixed, and the current ISO
is available for reinstalling. Please send bug reports, ideas, and feature requests through **Sloth Center →
Feedback**. I will review them as time allows.

Effort labels are rough implementation sizes: **Quick** (small, focused change), **Medium** (several components or
careful testing), and **Large** (broad work or significant safety and compatibility testing).

- [x] Replace the incorrect 1.0.2 ISO on SourceForge with the current build and publish its SHA-256 checksum.
- [x] Publish the installer fix and reinstall notice on GitHub and the website.

### Sloth OS 1.1 (release planned for 2026-10-27; tested as 1.0.5)
The `codex/1.0.5-test` branch, tested on a real machine (laptop) on 2026-10-26. Updates finish again (the rpm-ostree
crash, under 1.0.4 below); Sloth Center got a spotlight guide, Appearance (with an Ubuntu-like layout), Displays,
Sound, Bluetooth, a Wi-Fi check, programs that start at sign-in, app permissions, file restore and backup check;
the installer asks for the main screen and lets partitions be chosen; disc images open with a double-click. The
user-facing list is in `README.md`. Each item is under its topic (phases and the groups of 1.0.4 below).

Release:
- [x] The "Turn on Bluetooth" button on a real machine (2026-10-26: the rfkill block is lifted first, then Powered is
  set again while the adapter wakes up; checked on the laptop with the `cb41505` build)
- [x] Decide the number: 1.1 (2026-10-27; `files/scripts/branding.sh`, the README header; the SourceForge folder is
  `1.1`)
- [x] Finish the install when the installer starts the program at its end (the IrfanView bug, below)
- [x] Merge `codex/1.0.5-test` into `main` (2026-10-27; the `test/chunked-oci` branch stays out, see "Smaller system
  updates")
- [x] Build the ISO from `main`, install it once, upload it to SourceForge with its SHA-256 checksum (2026-10-27:
  `sloth-os-1.1-x86_64.iso`, 7.05 GB, SHA-256 `cccae10e7cb195563a0f73facf25a25da4829a038309d2b93170e53c5b91a735`;
  written to a USB stick, verified, and installed on a real machine without problems)
- [x] Website: the 1.1 news and download link (2026-10-27; the release notes fold out on the download page, as in
  the README)
- NVIDIA (2026-10-27): the gaming machine (RTX 5060) runs 1.0.4 without problems, with Secure Boot turned off.
  Secure Boot on (MOK enrollment) is still untested

Not checked on a real machine yet: the FPS display's temperatures, the metered-connection question (a phone
hotspot), disc images (eject, sign-out), the main-screen question and partition choice in the installer, the
self-healing installers, and IrfanView's installer with "Open IrfanView" ticked.

- [x] Choose the main screen in the installer (first page, only with more than one screen); the installer moves
  there at once, and the installed system makes it the main one at the first sign-in
  (`/usr/libexec/sloth-os/display-setup`). The login screen itself is not set yet. Check on a real machine
- [x] Other disks, "Use it": the Linux partitions can be chosen one by one, also on a disk with Windows (the
  Windows partitions are never mounted or changed). Check on a real machine
- [x] Disc images (.iso) open with a double-click: mounted read-only through UDisks (Dolphin shows it with an
  eject button); with an installer on it (autorun.inf, setup.exe) the .exe handler offers "Install from it" or
  "Open folder", and can remember the choice. Ejecting clears the loop device (autoclear), and images still open
  are ejected at sign-out (`sloth-disc-images.service`). Check on a real machine (a Windows program's ISO)

- [x] The Sloth Center first-run guide lights up what it talks about (2026-10-26): each step darkens the window
  except its pages in the list on the left (a pulsing frame around them), a bubble next to them explains, and the
  light slides to the next step's pages. A new step shows Appearance. Check on a real machine (also with a
  small window, and "Open guide" at the bottom of the list). Checked on a real machine (2026-10-26)
- [x] Appearance in Sloth Center (2026-10-26): the color schemes and taskbar layouts of the welcome wizard can be
  changed any time later. Both tools use the same code (`sloth_common/appearance.py`) and the same drawings
  (`sloth_common/qml/SlothCommon/LayoutPreview.qml`), so a layout looks the same whichever set it. New layout:
  Ubuntu-like (top bar with the date and time in the middle, a floating dock on the left that does not run into
  the top bar; the app grid slides out from the dock as the Start menu with large icons in a grid); GNOME
  itself is not added, KDE Plasma draws this look. Clicking the current layout in Sloth Center builds it again. Tests: `tools/tests/test_appearance.py`.
  Checked on a real machine (2026-10-26): every layout, switching back and forth, the pinned apps stay
- [x] Installers heal themselves and are remembered too (2026-10-26): what installed an installer before (here,
  or from the shared knowledge) goes first; if the installer crashes or its log shows a known missing component
  and nothing got installed, it is tried again with the fix or the next setting (another Proton version only into
  a new, emptied environment). A cancelled installer is not reopened (an error code alone does not count). What
  worked is kept in `~/.local/share/sloth-os/installers.json` and shared like the programs' settings. Tests:
  `tools/tests/test_install_heal.py`. Check on a real machine

### Sloth OS 1.0.4 (2026-10-26, replaces the unreleased 1.0.3)
Network, security and drive health on the System status and System health pages; what uses the space on the
Disks page and a deeper cleanup; the installer asks about the other disks; the .exe handler asks which drive a
program goes to; layer-by-layer update progress; every text in 50 languages.

- [x] **Critical** — Resolve the Fedora 44 `rpm-ostree` crash during OCI image updates (`2026.3-2.fc44` aborts
  with `JoinHandle polled after completion` while importing layers), then verify a full update stages and boots.
  (2026-10-26, real machine on 1.0.4: no crash this time; systemd stopped `rpm-ostreed` halfway when the
  `/boot` automount of systemd-gpt-auto-generator expired. 1.0.5: the automount no longer expires; a machine
  gets this with its first finished update, until then retrying continues from the layers already fetched.
  2026-10-26 evening, real machine on 1.0.5: a 2.3 GB update (23 new layers) went through, staged and booted.)
- [x] **Low** — `sloth-login-repair` failed at every boot on Fedora 44 (`Unknown profile feature
  [with-altfiles]`): it now only turns the feature on if the authselect profile still has it.
- [x] **Medium** — Show OCI layer progress in Sloth Center, stop the spinner and explain the failure if the
  transaction connection closes, and reconnect to `rpm-ostreed` after a daemon restart. Verify the flow without
  requiring a terminal. (2026-10-26: the Updates page shows "layer 3/29 · size" and the bar moves forward with the
  finished layers when rpm-ostree sends no percentage; check on a real machine with the next update)

#### Windows program launch follow-up (2026-10-22)
- [x] **Reddit Desktop in a Fedora box:** package installs now fail visibly if a new desktop entry uses `sloth-exe`,
  if export fails, or if the exported host `.desktop` lacks a `distrobox-enter` command or still invokes `sloth-exe`.
  The running Fedora box no longer has the Reddit package's source desktop entry, so a live relaunch could not be
  reproduced; `tools/tests/test_apps.py` checks that invalid exports cannot be recorded as successful installs.
- [x] **Medium** — Notepad++ starts again after closing: the install succeeded, but the start handler exited after 4–9 seconds
  and cycled through four runner settings even though the user saw the app open. Improve detection of a live Windows
  process after `umu-run` exits (check the prefix's Wine processes/wineserver), and only start another recovery attempt
  after confirming the previous app is no longer running. Reproduce that closing the app does not reopen it.
  (2026-10-26: after a quick exit the handler waits up to 6 s while anything, wineserver included, still runs in
  the environment; a clean exit (code 0, no error in the log) after 3 s counts as the user closing it and is not
  restarted. Check on a real machine with Notepad++)
- [x] **Medium** — 7-Zip required repeated installs: the saved log has one installer run, four quick-exit recovery attempts,
  and then a `7Z2605` Start menu entry. Reproduce the install and launch flow, then fix recognition or process tracking
  so a successful install is not mistaken for a failed app launch and repeated installation is unnecessary.
  (2026-10-26: the cause was that `7z2605-x64.exe` was not recognized as an installer, so it was run as a program
  and "healed" by running the installer again. Installers are now recognized by their contents too: known
  installer builders, or setup/install in the version information (7-Zip: "7-Zip Installer", checked on the real
  file). Check on a real machine)
- [x] **Medium** — Open `.iso` disk images with a double-click (idea, 2026-10-26): mount them without a password and
  show the contents. If the image has a `setup.exe` or an `autorun.inf`/`autorun.exe`, ask what to do (start the
  installer through the .exe handler, or just open the folder); remember the choice if the user asks. Offer
  "Eject" in Dolphin and unmount at sign-out.

- [x] **Medium** — Finish the install when the installer starts the program at its end (2026-10-26, real machine,
  IrfanView): with the installer's last "Open IrfanView" box left ticked, the program started from the installer
  and the install screen kept waiting; the Start menu question only came after the program was closed. Everything
  worked after that (installed, started without errors), but the user waits without knowing why. Likely cause: the
  `.exe` handler waits until the whole Windows environment is quiet, and the started program runs in it. Fix idea:
  treat the install as done when the installer's own process ends (or when a new program window of the installed
  program appears), ask the Start menu question then, and leave the running program alone.
  Done 2026-10-27: the cause was the recognition, not the waiting. The install only counted as done when it was
  certain what got installed (a shortcut, or the registry's uninstall entry), and Wine writes the registry to disk
  only later or when the environment stops, so with no shortcut it became certain only after IrfanView closed. Now
  a new .exe of the install that runs is enough (`detect.installed_running`; not in a temporary folder and not an
  installer itself), and the uninstall entry is saved afterwards, when the installer's environment stops. Tests:
  `tools/tests/test_apps.py`. Check on a real machine
  2026-10-27, real machine with the 1.1 build: it still waited. Without the log the cause is not known; the second
  round fixes the three likely ones: a reinstall (the .exe was not new), the contents check finding an installer
  builder's name inside the program, and Proton's helper processes keeping the installer's name in their command
  line after it exited. Now an .exe written during the install (its change time, which installers cannot set
  back) that runs is enough, by name only, whether the installer or its helpers still run or not.
  Third round, from the log (2026-10-27): the real cause. Only "iview476_x64_setup.exe" was ever seen running, even
  with IrfanView open: Proton gives Wine `WINEPREFIX=<prefix>/pfx/` (umu's `pfx` link points to the environment
  itself), and `library._prefix_procs` looked for the plain path, so it only found umu's own processes (whose
  command line has the installer's name) and never a Windows program. Now the resolved path is compared. This
  also affects "already running" at launch and the launcher hand-over watch (Battle.net), which saw only umu's
  processes too: check those on a real machine as well
- [x] **Small** — The same when reinstalling or updating into the existing folder: the program's .exe was already
  there before the install, so it was not "new". Done 2026-10-27 with the change time (above).
- [x] Done 2026-10-27: `sloth_exe/winui.py` (the marker files next to the program, or named in the last 1 MB of a
  single-file bundle), checked before the anti-cheat check when a program starts; the text in all 50 languages.
  Tests: `tools/tests/test_winui.py` (with .exe paths as arguments it tells what each one is; the real MAUI app:
  WinUI 3, its Avalonia rewrite: not). Check on a real machine.
  **Small** — Recognize WinUI 3 / .NET MAUI programs and say so in plain language instead of trying every
  setting (2026-10-27, a real .NET 10 MAUI app: `Microsoft.WinUI.dll`, `Microsoft.WindowsAppRuntime.dll`,
  `WebView2Loader.dll` in its single-file bundle). Wine cannot run WinUI 3 (DirectComposition, Windows App Runtime),
  so no Proton setting helps. Text like the anti-cheat one (`anticheat.maybe_text`): "This program is built on
  Windows' newest interface, which does not run on Linux yet." The bundle manifest of a single-file .NET app lists
  its files uncompressed, so the names can be read without running it.
- [ ] (Set aside 2026-10-27, not important for now) **Small** — An `.exe` on a USB stick or other FAT/exFAT/NTFS drive (every file looks executable there) must open
  with the `.exe` handler on a double-click: Dolphin offered to run it directly, and that failed with "failed to
  launch, status code: 203" (2026-10-27, real machine). Copied into Downloads it started fine.
- [x] Live mode: Windows programs start in the live system too (2026-10-27, real machine: an Avalonia .NET program
  ran without problems; the one that did not was the WinUI 3 / MAUI app above, which runs nowhere on Linux)
- [x] **Small** — Live mode, optional: run the bundled Proton and runtime from `/usr/share/sloth-os/windows-runtime`
  (writable there) instead of copying ~2 GB into a home folder that lives in RAM or on the USB stick: a faster
  first start and less memory. (2026-10-27: `windows-runtime-seed` links them in the live system (`rd.live.image`
  and the bundled folder writable), the installed system still copies; `windows-prepare` does not look for a newer
  Proton in the live system, that would download into the memory too. Tests: `tools/tests/test_runtime_seed.py`
  (installed, live, live but read-only, a second run). Check with the next ISO)
- [ ] (Set aside 2026-10-27, not important for now) **Small** — Ejecting a USB stick took about a minute ("closing the process") after `.exe` files were started
  from it (2026-10-27). Suspect: the runner uses the program's folder as the working directory, so Wine's
  background processes (wineserver) hold the stick for a while. Waiting for `fuser -vm` output; fix idea: a working
  directory outside removable drives, and stop the environment's background processes when the program closes
#### Installation and storage
- [x] **Large** — Ask what to do with additional disks and partitions during installation. Leave them untouched and
  unmounted by default; only format after explicit selection and confirmation, then offer automatic mounting.
  In the “Next to Windows” flow, protect Windows, EFI, recovery, MSR, and BitLocker partitions. Test both
  installation flows on multi-drive systems. (2026-10-26: "Other disks" on the disk page: leave it alone (default) /
  use it with its files (ext4, btrfs, xfs) / erase it for programs and games (btrfs; encrypted with a key file if the
  system is). A disk with NTFS or BitLocker can only be left alone, checked by the helper too. Mounted under
  /var/mnt with nofail; the erased disk belongs to the first user. Tested on loop disks
  (`tools/tests/test_extra_disks.sh`); still to test on a real machine with two drives, also next to Windows)
- [x] **Medium** — The .exe handler asks which drive a new Windows program goes to when there is more than one
  (with the free space, and "Always install here"); internal drives under /var/mnt or /run/media with a Linux file
  system are offered by themselves, USB sticks are not (2026-10-26; check on a real machine)
- [x] **Medium** — Before disk changes, run a compatibility check for boot mode, free space, Secure Boot, and Windows
  encryption or hibernation. Explain blockers and safe next steps in plain language. (2026-10-27: the installer's
  first page checks the computer (`sloth_installer.system.machine_check`): legacy BIOS mode blocks "Install" and
  says how to start in UEFI mode (the whole-disk install did not check this before; the helper refuses it too,
  before any disk is touched, `error.not_uefi`); less than 4 GB of memory and a laptop on battery are warnings;
  Secure Boot with an NVIDIA card is a note (Sloth Center asks for the key once after installing). Next to Windows,
  the disk survey already explained BitLocker, hibernation / fast startup, a disk to be checked, MBR, legacy mode and
  too little space; the disk list marks disks that are too small. Texts in all 50 languages. Tests:
  `tools/tests/test_machine_check.py`. Check on a real machine, also one started in legacy mode)
  2026-10-28, HP laptop: the battery warning stayed after the charger was plugged in; the first page now checks
  again every 3 s. Also from that install: with the 128-layer chunkah image the bar stood at 80% for minutes (the
  files are copied, bootc puts the system together and writes little); a new stage text says so ("Putting Sloth OS
  together… this can take a few minutes", all 50 languages). Both need a new ISO
- [x] Show the target disk and planned erase/resize/create/format/mount operations on the installer's confirmation page;
  the existing confirmation checkbox is required before applying changes. The temporary install partition is identified
  as mounted only during setup and deleted at the end.
- [x] Guide users through creating Sloth OS installation media, with a clear warning before erasing a USB drive.
- [x] **Medium** — With more than one display, let users choose the main display in the installer (idea, 2026-10-26):
  show the installer there, and carry the choice (main display, arrangement) over to the installed system's login
  screen and desktop.
- [ ] **Large** — Help users selectively migrate personal documents and supported browser data from Windows, with a preview.
- [x] **Medium** — Show storage health warnings when supported, and help users back up important files if a drive may be failing.
  (2026-10-26, System health: the drives' SMART reports through UDisks, with a File backup button; check on a real machine)
- [x] **Medium** — Identify reclaimable storage, estimate the space to be freed, and let users review items before cleanup.
  (2026-10-26, a first step: the Disks page shows what uses the space, and Clean up also removes the system's
  temporary files and cached update data. 2026-10-27, the review: "Clean up…" first measures and lists the items
  with their size, each with a tick box: temporary files not used for a month (~/.cache, except Sloth OS's own
  folder: the self-healing logs and the shared knowledge; links are not followed), the Trash, components no app uses
  anymore (Flatpak), Windows installers already used (in the home folder, from the programs' records; not ticked by
  default, they are the user's own files), and the system's temporary files (rpm-ostree, administrator approval,
  size only known afterwards). Only the ticked ones are deleted; the result is the space really freed.
  `sloth_center/cleanup.py`, tests: `tools/tests/test_cleanup.py`. Check on a real machine)

#### Sloth Center, setup, and support
- [x] Add a system status page with OS version, update status, available storage, and a direct Feedback link.
- [x] Offer a short first-run guide to Updates, Programs, Games, backups, Feedback, and Disks; users can skip it or
  reopen it from the sidebar.
- [x] **Medium** — System and driver overview for graphics, audio, Bluetooth, and connected peripherals (2026-10-26):
  the Drivers and hardware page has the graphics card, Displays, Bluetooth (no adapter / off with "Turn on
  Bluetooth" / the connected devices with battery, "Pair a device"), Sound and Controllers. Bluetooth is read from
  BlueZ with a short timeout in the background: without an adapter the service does not start and asking it would
  wait (found on the developer machine). It follows the tray (refresh every 3 s while the page is open) and counts an
  rfkill block as off; "Turn on Bluetooth" lifts the block and sets Powered again while the adapter wakes up.
  Tests: `tools/tests/test_bluetooth.py`. Checked on a real machine (2026-10-26)
- [x] **Medium** — Application privacy overview (2026-10-26): Account and security → "App permissions" lists
  the Flatpak apps that can use the camera (all devices, or the camera portal), the microphone (the sound socket,
  or PipeWire directly) and the location (the location portal). It only reads; "Change app permissions" opens
  KDE's Flatpak permissions page (a switch here would also take the speaker or the game controllers away).
  Tests: `tools/tests/test_privacy.py`. Checked on a real machine (2026-10-26)
- [x] **Medium** — Add a security overview for disk encryption, Secure Boot, and updates, with plain-language guidance.
  (2026-10-26, a Security card on the System status page; check on a real machine, with and without encryption)
- [ ] **Large** — Offer a privacy-reviewed diagnostic bundle for Feedback. Redact personal data, let users review it, and
  require their choice before attaching it.
- [x] **Medium** — Guided Wi-Fi troubleshooting (2026-10-26): System status → Network → "Check Wi-Fi". Step by
  step in plain language: is there an adapter (if not: Drivers and hardware), is it turned on (a key or switch on
  the computer, or "Turn on Wi-Fi"), is it connected ("Choose a network"), how strong the signal is, does the
  internet answer (a sign-in network: "Open the sign-in page"; no internet: restart the router). It reads
  NetworkManager and rfkill only. Tests: `tools/tests/test_wifi.py`. Checked on a real machine (2026-10-26); a hotel
  or train network not yet
- [x] **Medium** — Keep essential installation, recovery, and troubleshooting help available offline.
  (2026-10-28: Sloth Center → Help (`HelpPage.qml`), built in, nothing downloaded: Sloth OS doesn't start (the
  boot menu shows itself after a failed start, or Esc / Shift; the second entry is the previous version; "Reset
  this PC" in the same menu), an update caused trouble, no internet / Wi-Fi, a missing or overwritten file, a
  Windows program or game doesn't start, no sound, the screen looks wrong, installing again or on another
  computer (save the settings file first), asking for help. Each answer has a button to the page that fixes it
  (`openModuleById`). In every language the answers quote the page and button names from that language's own
  translations, so they match the screen. Check on a real machine)
- [ ] **Large** — Make temporary, limited guest accounts easy to create without exposing the owner's personal files.
- [ ] **Large** — Provide accessible controls for text scaling, contrast, screen reader, and keyboard navigation.
- [x] **Medium** — Manage startup applications (2026-10-26): Services page, "Programs that start when you sign
  in": the user's own autostart entries (Steam, Discord, … also those added through the Flatpak background portal)
  with their name, description and a switch (`Hidden=true`, as KDE's own settings do). The system's parts
  (/etc/xdg/autostart) are not listed, turning those off would break something. The startup impact is not shown:
  it cannot be measured reliably. "Add a program…" opens KDE's autostart settings: Steam's own "start with the
  computer" option cannot write there from its Flatpak. Tests: `tools/tests/test_startup.py`. Checked on a real
  machine (2026-10-26, Steam added and turned off)
- [ ] **Large** — Gather laptop power-saving and performance modes, display and sleep settings, and supported battery
  health or charge limits in one place, with clear effects on battery life and gaming.

#### Updates, backup, and recovery
- [x] **Quick** — Explain that updates download the needed system parts, their size varies, free disk space is needed, and a restart applies the new version.
- [x] **Medium** — Avoid restart prompts during user-defined quiet hours (2026-10-27): Updates → Quiet hours, on/off
  and from / to in whole hours (over midnight too). The notifications that ask for a restart (an update is ready,
  the NVIDIA driver is ready) do not speak then and come again when the quiet hours end (a one-time user timer,
  `systemd-run --user`); nothing restarts by itself. It goes into the settings file too.
  `sloth_common/quiet_hours.py`, tests: `tools/tests/test_quiet_hours.py`. Check on a real machine
- [x] **Medium** — Let users choose when the automatic updates download (uupd's timer; needs administrator approval).
  (2026-10-28: Updates → "When system updates download", an hour list. The first version set `uupd.timer`, but the
  image has no uupd (the HP did not show the card): the system update is `rpm-ostreed-automatic.timer` (an hour
  after start, a day after the last run, and 4:00 from Universal Blue's `override.conf`; never on a metered
  connection, the service's `ExecCondition`), and it does not wait for a busy computer, so that sentence went.
  `sloth-helper update-time <hour>|default` writes `zz-sloth-time.conf`, which clears every trigger and sets only
  the chosen hour (`Persistent`: at the next start if the computer was off); the name must sort after
  `override.conf`, `50-` did not (checked with `systemctl cat` in the image). Also under `sloth-helper-versions`;
  one approval per change (a list, not a spin box). App updates (`flatpak-system-update.timer`, 2 minutes after
  start) are not changed. Tests: `tools/tests/test_update_time.py`. Check on a real machine: `systemctl
  list-timers rpm-ostreed-automatic.timer` after choosing an hour)
- [ ] (Not doable as asked) Limit the update download speed: neither rpm-ostree / bootc nor Flatpak can limit it.
  What it is for is covered: the automatic update waits while the computer is busy, and the hour can be chosen.
- [x] **Medium** — Warn before large downloads on metered or mobile connections (2026-10-26): the Updates page shows
  the download size of the waiting update, and "Install update" on a metered connection asks first ("Download
  anyway" / "Later"). The automatic update (rpm-ostreed-automatic) already skips metered connections. The size: checked on a real
  machine (2026-10-26); the metered question (a phone hotspot) not yet
- [ ] **Medium** — Smaller system updates (measured 2026-10-26 on ghcr): every build rebuilds all 23 of our own
  layers, so even a one-line change downloads about 2.3 GB (with the daily base image changes 3.8 GB) of the
  6.5 GB image; the two biggest are the gaming `dnf` module (~800 MB) and the umu/Proton script (~840 MB).
  Rechunking (BlueBuild `rechunk`, content-based layers) would download only what changed. The first update after
  the switch is a full download; check the installer (`ostree.final-diffid`) with a rechunked image first.
  Tried 2026-10-26 on the `test/chunked-oci` branch (`build_chunked_oci: true`, plus an install-test CI job):
  the first build worked (129 layers, 4.7 GB instead of 6.5 GB; `ostree.final-diffid` present, so the installer
  check passes), but every later build crashes in rpm-ostree 2026.2 when it uses the previous image as the
  baseline (`ostree-ext/src/chunking.rs:423` assertion, `left: 845, right: 0`). Wait for a fixed rpm-ostree, or
  try BlueBuild's `chunkah` option instead.
  `chunkah` (2026-10-27/28, same branch): every build works (128 layers, 4.5 GB image, the ISO 5.2 GB instead of
  7.05 GB); the CI install test passes; installed on the HP laptop from a test ISO and updated on it. Downloads: a
  one-line change ~1.05 GB, the whole 1.1.1 work 1.6 GB, a rebuild with nothing changed still ~1 GB (12 of 128
  layers differ every build: find which and make them reproducible). Before it goes to `main`: the build pulls
  `quay.io/coreos/chunkah:latest` every time, and a quay.io outage (502) failed a build (2026-10-28): pin a version
  if BlueBuild allows it; the installer's 80% step is longer with 128 layers (a stage text says so now). The HP
  laptop stays on the branch image for good: it is the preview machine, two steps ahead of the release.
  2026-10-28: `normalize-mtimes.sh` (fixed times for files changed in the last 3 days, before the initramfs and at
  the end): a rebuild with nothing changed went from ~1 GB to 353 MB (3 of 128 layers); the CI now also boots the
  installed disk in a UEFI VM (`sloth login:` reached).
- [x] Show backup availability and last backup time in Sloth Center (File backup page).
- [x] **Medium** — Let users schedule file backups, choose retention, and estimate required storage. (Closed
  2026-10-27: the backup runs every hour by itself (`sloth-home-snapshot.timer`, also caught up after the computer
  was off) and "Back up now" is on the page; the keep time is chosen there (2 weeks / 1 month / 3 months: every hour
  of the last day, then one a day, then one a week; the oldest go sooner when the disk is filling up). A separate
  schedule is not offered: a snapshot only stores what changed and takes a moment, so hourly is right for everyone.
  The storage is not estimated in advance: Btrfs snapshots share the unchanged data, so a number would be a guess;
  the Disks page shows the space really used ("System, earlier versions and other").)
- [x] **Medium** — Guide users through restoring a selected file (2026-10-26): File backup → "Restore a file…"
  (pick the file) or "Find deleted files…" (pick the folder it was in) opens the same "Previous versions" window
  as right-click in the file manager, for those who do not know that menu. Checked on a real machine (2026-10-26)
- [x] **Medium** — Verify backups by checking that the saved states can be read (2026-10-26): File backup →
  "Check the backup" reads back a sample of 300 files of the latest saved state (no password, nothing changed)
  and says in plain language whether all of them can be read; files the user may not read anyway are not
  counted as a fault. Tests: `tools/tests/test_backup_verify.py`. Checked on a real machine (2026-10-26)
- [x] **Medium** — Back up and restore Sloth OS settings after reinstalling or when moving to another machine.
  (2026-10-27: File backup → Sloth OS settings: "Save settings to a file…" / "Load settings from a file…". The file
  (readable JSON) holds Sloth OS's own settings files (sharing, the disc image choice, the display and sound profiles,
  where Windows programs go, the developer panel) and the look (color scheme, taskbar layout). Nothing personal.
  Loading writes only these files back (whatever the file says), keeps a program location only if that drive exists
  here, and sets the look again. `sloth_center/settings_backup.py`, tests: `tools/tests/test_settings_backup.py`.
  Check on a real machine)
- [x] **Medium** — Reinstall the apps too when loading the settings (2026-10-27): the settings file keeps the installed
  apps (their Flatpak ids); after loading, "Install them with Sloth Welcome" opens the wizard at the first app step
  with them ticked (`welcome-progress.json`, added to a selection already there; the passwords and sharing steps
  are not shown again). The wizard keeps only the apps its catalog knows and does not install again what is there.
  Windows catalog apps (e.g. Battle.net) are not in it yet. Tests: `tools/tests/test_settings_backup.py`. Check on
  a real machine
- [ ] **Large** — Protect game saves, including saves without built-in cloud support; show backup status and help restore them.
- [x] **Medium** — Offer system rollback after an update from Sloth Center, with a clear explanation and restart
  flow (already on the Updates page: the explanation, a confirmation that files and settings are kept, then
  "Restart now"; earlier versions can be kept and started there too)
- [ ] **Large** — Before significant settings or driver changes, offer a recoverable state and a clear way to revert.

#### Gaming, devices, and connectivity
- [ ] **Large** — Add an optional gaming mode that applies performance and notification settings while a game runs, then
  restores normal settings when it closes.
- [x] **Medium** — Performance display for frame rate, system load, and temperatures (2026-10-26): the per-game
  "Show FPS and performance while playing" (Games page, MangoHud) showed the frame rate and the CPU and GPU load;
  turning it on now also writes a MangoHud.conf with the CPU and GPU temperatures and the memory, for Windows
  programs and in Steam's Flatpak folder, only where there is none yet. Tests: `tools/tests/test_overlay.py`.
  Check on a real machine (a Steam game with the FPS display on)
- [x] **Medium** — Test and select controllers, microphones, and audio output devices before gaming (2026-10-26):
  Drivers and hardware → Sound: choose the speakers or headphones and the microphone (the default for games and
  calls), "Play a test sound", "Test the microphone" (records four seconds, says whether it heard anything, plays
  it back), and a muted microphone can be unmuted. The controllers were already there (list, battery, pairing,
  "Test the buttons"). Tests: `tools/tests/test_sound.py`. Checked on a real machine (2026-10-26)
- [ ] **Medium** — Share concise, community-informed game fixes with version details and a way to report outdated guidance.
- [ ] **Large** — When a game fails or crashes, offer a readable diagnostic summary and relevant, verifiable fixes.
- [x] **Medium** — Help users move supported game libraries between drives without downloading again, updating launcher paths.
  (2026-10-28, Steam: Games → each Steam game shows its drive and size, and "Move to another drive…" lists Steam's
  own folder, the libraries Steam has, and a `SteamLibrary` folder on every other internal Linux drive (USB sticks
  left out). `sloth_common/apps/steam_library.py` moves what Steam's storage manager moves: the files, the Proton
  environment (`compatdata`, part of the saves), the shader cache and workshop content, then the manifest last, and
  updates `libraryfolders.vdf` (registering a new library with its `libraryfolder.vdf`). Same drive: a rename;
  another drive: copy, size check, only then delete the old one; a failed copy leaves the game where it was. The
  Flatpak Steam gets a user filesystem override for the new library. Steam must be closed (the page offers it).
  Tests: `tools/tests/test_steam_move.py` (rename, copy, a copy failing halfway, refusals, a manifest pointing
  outside the library). Heroic / other launchers: not yet. Check on a real machine with a second drive)
- [x] **Quick** — Show network status and latency, with basic guidance when the connection may affect online play (2026-10-23, Sloth Center's System status page).
- [ ] **Medium** — Help configure NAS devices and shared folders, preserving the connection after restart when requested.
- [ ] **Large** — Allow consent-based file sharing with another device on the local network without a cloud service.
- [x] **Medium** — Monitor refresh rate, VRR and HDR for gaming (2026-10-26): Drivers and hardware → Displays.
  Each monitor by its own name (EDID), its refresh rate now and the highest at the same resolution with a "Use
  144 Hz" button (found on a real machine: a 144 Hz monitor running at 100 Hz), and switches for VRR and HDR only
  where the monitor supports them, through kscreen-doctor. After a change it asks "Keep?" and goes back by itself
  after 15 seconds, as KDE's own display settings do. The resolution stays in "More display settings".
  Tests: `tools/tests/test_display.py`. Checked on a real machine (2026-10-26)
- [x] **Medium** — Let users save and quickly switch display and audio profiles, such as desktop, TV, or headset setups.
  (2026-10-27: Drivers and hardware → Display and sound profiles. A profile is the monitors' state (on or off, size,
  refresh rate, position, scale, main one) and the default speakers / headphones and microphone, saved with a name
  from the current setup and applied with one click through the Displays card's "Keep this setting?" (going back
  puts the sound back too). Only connected monitors are changed, a missing one is left out and named; a profile
  that would turn every screen off is not applied; the mode is found again by size and refresh rate.
  `sloth_center/profiles.py`, tests: `tools/tests/test_profiles.py`. Check on a real machine, also with a TV)
- [x] **Medium** — Maintain hardware and game compatibility notes, including which GPU, controller, and settings worked well.
  (2026-10-28, together with the "Will it run?" idea: Games → "Will it run?", a search over ~20 000 games. Marks:
  🟢 runs well (85%+ of the reports say it works), 🟡 runs but may have issues (50%+), 🟠 often doesn't start,
  🔴 blocked by its makers (AreWeAntiCheatYet "Denied": "Not Sloth OS's fault…") or by its anti-cheat ("Broken"),
  🦥 tested by Sloth OS, ⚪ too few reports. Each result says how many players report it working, the share per
  GPU vendor (AMD / NVIDIA / Intel), the anti-cheat, a Linux version, and whether the shared knowledge has a
  working setting (applied by itself; no "Proton" wording). Installed Steam games show their mark too. Data: the
  knowledge repository's `games-index.json` (monthly, `seed/games_index.py` from ProtonDB (ODbL) and
  AreWeAntiCheatYet (MIT); `sloth-tested.json` by hand), downloaded weekly by Sloth Center and kept for offline use.
  `sloth_common/game_check.py`; tests: `tools/tests/test_game_check.py`. Controllers are not in the data
  (ProtonDB has no controller field); a later step could add them to `sloth-tested.json`)

### Sloth OS 1.0 released (2026-10-21)
The repository is public (`Sloth-OS-Linux/sloth-os`), the daily build is back on, the installer ISO is on SourceForge
(`1.0/sloth-os-1.0-x86_64.iso`, 6.2 GB, SHA-256 `ed01d760…a4ddbe`), and the website has a download page with system
requirements and a USB guide. Since the release the whole repository is in English (comments, documentation, commit
messages); Sloth Center's translation keys are English sentences.
- [x] Make the two images public on ghcr.io (2026-10-21; it needed "Public" under the organization's Settings → Packages →
  Package creation first); installed machines update without signing in
- [x] Redeploy the shared knowledge Worker (2026-10-21; the feedback issues' text is English now)
- [x] **Sloth OS 1.0.1** (2026-10-21): the installer no longer offers the Ventoy stick it runs from as an install target
  (tested in a VM with Ventoy 1.1.18), and Windows installers count as done as soon as the installed program runs
  (Battle.net's login window). ISO on SourceForge (`1.0.1/sloth-os-1.0.1-x86_64.iso`, SHA-256 `e0729d30…71bf3`), the
  website's download page points to it

### Next steps (2026-10-20 evening, in order; details below)
**Required before publishing**
1. [x] File backup and "Previous versions" (To do, item 8): done (2026-10-20), the test below
2. [x] Resetting the computer from Sloth Center: done and tested on a real machine (2026-10-20); the boot menu
   variant later
3. [x] **The whole test on a real machine, after a full reset, with the latest image** (below: "Test after the
   2026-10-20 reset")
4. [ ] Old (BIOS-only) machines (To do, item 2): after 1.0 (decision: 2026-10-20, 1.0 is UEFI only)
5. [x] A new ISO with squashed layers once the system is ready (including the installer fix: black screen after 90%)
6. [ ] Native-speaker review of the translations (To do, item 7): it will come through feedback
7. [x] Last: making the repository public, daily build, ISO hosting (To do, items 3–4). The website already exists:
   https://github.com/Sloth-OS-Linux/sloth-os-linux.github.io

### 2026-10-20 evening: what happened (in short)
- **VM test** on the 13:36 image (Welcome, Battle.net, EA app, Ubisoft, Updates, File backup, zram): the bugs found
  are fixed (EA Start menu and recipe, the Previous versions buttons, Wine sample programs, Programs browser, Games
  drop-down), details below ("Bugs of the VM test")
- **New:** Feedback from Sloth Center (live: `Sloth-OS-Linux/feedback`, in 50 languages), password-free "Back up
  now", Welcome continues after an interruption, reset from the boot menu (the files stay)
- **Installing next to Windows in a VM:** two serious bugs fixed (the boot loader went onto the Windows EFI partition;
  the boot menu did not come up on any machine, because `${cmdpath}` was empty). Installer fix: needs a new ISO
- **After fingerprint + PIN the login screen did not start** (on the developer's machine): authselect removed
  `with-altfiles`; fixed, and at startup it also repairs machines already broken
- Website: real screenshots, a Sloth Center section, FAQ (feedback); shared knowledge: EA recipe (PR #1, merged)
- Decisions: 1.0 is for UEFI machines only (BIOS later); parental controls and Windows programs in Discover after 1.0

### Summary of 2026-10-21 evening (the 14:01 ISO, installer `c466ce8` + image `887dcf1`; on two USB sticks)
**Tried on a real machine (HP), works:** encrypted whole-disk install, Welcome continuing after an interruption,
Sloth Center on the taskbar, PIN and fingerprint (without a false error message), boot menu and reset (a backup before,
warnings), feedback with a log (#5), File backup and Previous versions, EA app (the installer does not spin), Games page,
muting, Heroic/Epic, zram, taskbar balloon on the right, WoW Classic from Battle.net.
**Still open:**
- [x] Running Welcome again on an existing system (ticks, current appearance): works well on the new install
- [x] **Installing next to Windows (with and without encryption):** the loop-disk tests pass for both (below); a real
  Windows VM was not run, which the user accepted as sufficient for now (2026-10-22)
- [ ] NVIDIA machine (at home, the developer machine: RTX 5060 + AMD iGPU): Drivers and hardware page, Secure Boot MOK
- [ ] Steam takeover, firmware in Discover
- [x] **Support (Ko-fi, `ko-fi.com/slothos`, 2026-10-21):** a quiet link on Sloth Center's Feedback page and on Welcome's
  last page (in 50 languages; the address is in the text too, in case there is no browser), README, `.github/FUNDING.yml`
  (GitHub "Sponsor" button), the website's footer and FAQ
- [x] **Moved to the Sloth-OS-Linux organization** (2026-10-21): `sloth-os` and `sloth-os-knowledge` moved, the
  secrets stayed, the first build to the new place (`ghcr.io/sloth-os-linux/sloth-os(-nvidia)`) is fine. The packages
  are still private: set them public in Package settings when going public. The old `ghcr.io/bathorizsolt/…`
  images can be deleted after the final ISO
- [x] **ISO hosting: SourceForge** (2026-10-21, free, unlimited, with mirrors): sourceforge.net/projects/sloth-os,
  user `slothos`; upload with SFTP/rsync (`frs.sourceforge.net:/home/frs/project/sloth-os/`), the key on this
  machine: `~/.ssh/sloth_sourceforge` (tried). Metadata, categories, logo done
- [ ] Checking the name by hand (TMview, SZTNH); web search 2026-10-21: there is no operating system called "Sloth OS"

### The test of 2026-10-21 (real machine, reinstalled from the morning ISO, `d43e36f`)
The ISO was built locally (`out/sloth-os.iso`, 08:33, from the `latest` image, with the installer fix in it).
1. [x] **Image version:** fresh ISO, the `d43e36f` image
2. [x] **Welcome interrupted:** continues from there, remembered everything
3. [x] **Sloth Center on the taskbar**
4. [x] **Fingerprint + PIN:** the PIN works. For the fingerprint "administrator password needed", and after enrolling,
   unlocking with a finger does not work. Checked in a container: it is correct (it turns on `with-fingerprint` next to the
   PIN profile too), but **the login screen's (`plasmalogin`) PAM uses `password-auth`, which has no fingerprint**:
   after a restart the finger never works, only on the lock screen (`kde-fingerprint`) and for approvals. To clarify:
   where it was tried (after a restart / Win+L), what the exact message was, and whether the switch stayed on
5. [x] **Boot menu:** comes up with Esc, the entry is in the system's language (English), it runs
6. [x] **Feedback:** "Couldn't send it" with a log attached. **Fixed:** Sloth Center cut the log to 500 KB in raw
   bytes, the service looks at the whole request (576 KB); JSON encoding blew up the non-ASCII characters and the
   backslashes of Wine logs, so a 413 came back. Now it keeps the encoded request under the limit (tried on the live
   endpoint: old encoding 413, new 200). The tries are in the feedback repository: #2, #3, #4 (closed). Try again on a real machine
7. [x] **File backup:** "Back up now" without a password, the Previous versions buttons, restoring: all good. Request: a
   backup is needed before a reset. **Done:** in "Keep my files" mode the reset makes a saved state by itself (also when
   started from the boot menu); in "Remove everything" mode a warning (the backups on the machine are deleted too),
   a Pika Backup button, and you can only go on after ticking "I have saved what I need". Website: FAQ and home page
   (`sloth-os-linux.github.io`)
8. [x] **EA app:** installs, it is right in the Start menu, starts from there. **Bug:** at the end of the installer the EA
   app starts, the installer does not exit until then, and the .exe handler spins ("still downloading a few components")
   until the EA app is closed from the taskbar. **Fixed:** the end of the install is now watched while the installer runs
   (if the installed program certainly exists and already runs: done); the still running installer is not killed, it is
   waited for in the background; Welcome's queue moves on meanwhile (`sloth-exe: queued-done`). Instead of the
   misleading "download" text, "Finish the installation…" as soon as the installer runs. Try again on a real machine
9. [x] **Games page:** the upscaling drop-down is right
10. [x] **Balloon:** in the mac-like layout it still comes from the top left corner (from the "start" button). Likely cause:
    Wine aligns it inside the work area, below the panel with a top panel, but `wine-balloons` looked for it within
    64 px of (0,0). **Fixed:** it measures from the work area's corner, with a bigger margin when scaled. Check it in the
    Windows layout too. WoW Classic starts from Battle.net
11. [ ] If there is time left: zram is good (22.4 GB compressed reserve with 15 GB of memory); firmware in Discover not
    yet; Steam takeover later
- [x] HP laptop with encryption: fine (2026-10-21 afternoon, tried again)

#### Second round (2026-10-21 afternoon, with the `5bec760` image)
- [x] HP + encryption good; reset: the warnings show, everything works; EA installer good;
  muting: gone; Heroic works with the Epic account
- [x] **Fingerprint:** turns on, works perfectly after a restart, but Sloth Center shows a red error ("administrator
  approval needed"). On the real machine `authselect` returns an error code while switching (it does not happen in a container).
  **Fixed:** the helper checks whether the feature really switched, the error text goes to the log
- [x] **Feedback still did not go out:** Cloudflare blocks Python's default User-Agent ("Python-urllib")
  (403, error 1010), the request did not even reach the service. **Fixed:** a custom User-Agent (tried on the endpoint:
  it reaches the service). Again on a real machine
- [x] **Balloon in the mac-like layout still at the top left** (at the sloth head). The service is in the image and turned
  on. **Fixed / investigation:** it watches the top left third (the small windows of tray icons are skipped), a fallback
  recognition from `_NET_WM_PID`, and it logs everything (`wine-balloons`: "balloon: …" / "popup window, left alone: …");
  tried on Xvfb. If it is still wrong on a real machine: Save log, and the `wine-balloons` lines will tell
- [x] **Running Welcome again on an existing system** (request): the already installed apps with a tick and an "Already
  installed" label (Flatpak: their folder; Windows program: the .exe handler's records, with a Start menu entry), they are
  not installed again; the current color scheme and taskbar layout are the defaults (from Plasma's settings). Tried
  offscreen in the image
- [x] Feedback with a log: works (#5); fingerprint: fine
- [x] **The encrypted install failed with the 12:52 ISO** ("Something went wrong while copying…"): yesterday's
  `hide_other_esps` asked for the partition numbers with `lsblk`, and the open encrypted layer (`/dev/mapper/
  sloth-root`, without a number) came first in the list → TypeError, the copy did not even start (the morning ISO did
  not have this yet). **Fixed:** the number comes from the kernel (`/sys/class/block/<partition>/partition`); tried on a
  loop device with an open LUKS. New ISO
- [x] **Install test in a container** (`tools/tests/install/`: `all.sh [full|full-enc|win|win-enc]`, on the podman machine
  or on Linux, as root; in the live image, on a loop disk, from the ISO build's storage; UEFI faked). Result 2026-10-21 (14:01 ISO):
  - full-enc and full: the install runs (about 12 minutes), LUKS2 opens with the password, language/keyboard/time zone/account fine.
    There was no boot loader on the EFI partition, because it ran without UEFI (the faked UEFI run is still to do)
  - **win and win-enc: they run, 0 errors** (2026-10-21 evening, on Linux: `SLOTH_BUILD_DIR=/mnt/adatok/sloth-iso-build
    SLOTH_TEST_DIR=… all.sh win win-enc`; UEFI faked, the helper from the repository): NTFS shrinks from 100 to 55 GB, intact,
    the file on it unchanged; the boot loader on its own EFI partition, the Windows EFI partition untouched, the
    Windows entry in the boot menu, the menu is shown; LUKS2 opens with the password, crypttab and `rd.luks.uuid` fine; local
    time. Still to try on a real Windows machine (whether Windows starts afterwards, the boot menu)
  - **Retest 2026-10-22, current source:** fresh ISO built with Podman storage on the data disk; `win` passed 18/18 checks,
    `win-enc` passed 22/22. Both verify the Windows EFI partition and NTFS user file stay intact. The custom-storage test
    runner now gives the live container the same graphroot path as the host. A real Windows VM was not run; the user
    considers the loop-disk results sufficient.
  - Note: on WSL the disk files go to C: (the WSL disk is sparse, the test runs fstrim after each case); once
    C: filled up (1.4 GB), and WSL crashed. One case needs about 15 GB of free space
- [x] The installer's error page: a "Save log…" button (by default onto the plugged-in USB stick), instead of the `/tmp` path (in 50 languages)
- NVIDIA: will turn out at home; until then the website says "at your own risk, not tested yet". Next to Windows: soon.
  Steam takeover later

### Test after the 2026-10-20 reset (latest image, real machine)
Checked in advance in a VM (2026-10-20 evening, the 13:36 image, `71b9b89`, encrypted disk, open network); what was
fine there needs to be checked only once on a real machine:
- [x] (fixed 2026-10-20 evening, below) **Welcome, interruption:** in a VM (restarted suddenly while Steam was installing): Welcome starts from the beginning,
  the choices (language, apps) are lost, it does not mark the already installed apps (it offers them again). Choosing them again, it ticks
  the installed ones at once and installs the rest; the end is fine. It works, but it is inconvenient: see below, bugs
- [x] **First .exe on a fresh system:** in a VM the Battle.net installer appeared within 20 s (2026-10-20)
- [ ] **Battle.net:** in a VM it installs, starts, the login window comes; starting a game on a real machine (needs an account)
- [ ] **EA app:** in a VM it installs from Welcome and starts (2026-10-20). Bugs (fixed, below): it did not get into the
  Start menu, the helper programs were ticked on the list. On a real machine: whether it starts from the Start menu, also
  after the EA app's own update (when closed it had just updated: the link already pointed to the new version)
- [x] **Ubisoft Connect:** in a VM it installs, starts, stays open (1 minute), the Start menu entry is right
- [ ] **Taskbar balloons:** without signing in none of the launchers goes to the taskbar; on a real machine, with an account
- [x] **Updates page:** in a VM the version is right (Sloth OS 1.0 (Fedora Atomic 44) · date), after a check it says
  "up to date" (correctly), the previous version can be restored; the system update runs with a signature (`ostree-image-signed`).
  The "there is a new version, but it says up to date" bug was only shown by the old (10-19) image, before updating
- [x] **Snapshots and "Previous versions":** in a VM: 2 saved states after "Back up now"; the overwritten file is the original
  after Dolphin right-click → "Previous versions" → Restore. Bug (fixed, below): the buttons had no text
- [x] **zram** (Advanced settings): in a VM after "Larger" and a restart 7.7 GB → 11.6 GB (with 8 GB of memory)
- [ ] **Steam takeover and migration:** needs a Steam account (on a real machine)
- [ ] **Firmware:** whether the BIOS/firmware shows on Discover's Updates page (fwupd); nothing to check in a VM
- [ ] **Sloth Center on the taskbar:** whether it is there for a new user (after the reset); for existing users it does not
  appear by itself (only when changing the layout), that is how it was in the VM
- [x] **Installing next to Windows, in a VM** (2026-10-20, with a "Windows" test disk: GPT, a Windows EFI partition
  with `bootmgfw.efi`, MSR, an 80 GB NTFS with 2 GB of data; the 10-19 ISO, with the fixed installer helper). Good: recognition
  ("Has Windows on it", "Next to Windows" by default, max. 57 GB), the confirmation page, shrinking and installing (without a
  black screen), NTFS intact (the files are there), the clock (`adjtime: LOCAL`), the boot menu for 5 s, with Windows in it (the
  chainloader reaches the Windows boot loader) and "Reset this PC". **Two bugs, fixed:**
  - The boot loader went onto the **Windows EFI partition** (bootupd picks the disk's first EFI partition, not the
    mounted one), ours stayed empty, the boot menu's files went nowhere. Fixed (`sloth-install-helper`,
    `hide_other_esps`): for the duration of the install the other EFI partitions' type is "Microsoft basic data", then back
  - **The boot menu did not come up on any machine** (neither after a failed start nor next to Windows): `custom.cfg` used
    `${cmdpath}`, which is empty there because of bootupd's `configfile` (checked in the GRUB console). Fixed
    (`grub-custom.cfg`): our own EFI partition is found by `search --file /EFI/fedora/sloth-boot.env` (`sloth_dir`,
    exported for the menu entries). Existing machines get it with the next image (`boot-env ensure-config`)
- [x] The installer's confirmation page says that after shrinking, Windows may show "Scanning and repairing drive"
  on its first start, and tells the user to keep the computer plugged in until it finishes.
- [x] A new ISO with the installer fix (`hide_other_esps`); then on a real machine, next to a real Windows (tester)
- Later, when there is a machine / tester: an NVIDIA machine (the gaming machine), a BIOS-only machine, printer and scanner

**Bugs of the VM test (2026-10-20 evening)**
- [x] **After turning on fingerprint and PIN the machine did not get to the login screen** (2026-10-20 evening,
  real machine; reproduced in a VM). Not PAM: on every change (fingerprint, PIN, work account) authselect
  rewrites `/etc/nsswitch.conf`, and without `with-altfiles` it removes `altfiles` from it; on an Atomic system the
  system users (including the login screen's `plasmalogin` user) are in `/usr/lib/passwd`, so the
  login screen exited at once ("getpwnam_r( "plasmalogin" ) username not found"). Fixed (`sloth-helper`):
  `keep_altfiles` after every authselect change (at `select` right away), and `sloth-login-repair.service` at startup,
  before the login screen, also on machines already broken. In a VM: after the fix the login screen comes back,
  and one can sign in with a PIN with fingerprint turned on too. On a real machine: fingerprint + PIN again
- [x] **EA app: it did not get into the Start menu.** `EADesktop.exe` was on the list twice (from the main and the `compatibility32`
  folder), the entry's name is made from the file name, so the ticked row created it and the unticked one deleted it right away.
  Fixed (`sloth_exe/controller.py`, `confirmShortcuts`): an unticked row does not delete what a ticked one asks for
- [x] **EA app: the helper programs (App Recovery, Error Reporter, Updater) were ticked, EADesktop was not.** There was
  no EA recipe. Fixed: the `ea-app` recipe (`recipes.json`, `updated` 2026-10-20; prefer `eadesktop.exe`, the helpers
  skipped); it must go into the shared knowledge repository too (otherwise the newer downloaded file overrides it)
- [x] **EA app: the Start menu would have pointed to the versioned folder** (`EA Desktop\13.809.0.6322\…`), which disappears
  after the EA app updates. Fixed (`detect._via_link`): instead of the versioned path, the one through the link next to it
  (`EA Desktop\EA Desktop\EADesktop.exe`); with equal scores the shallower path without a version number wins. Test:
  `test_ea_app_versioned_dir`
- [x] **Wine's sample programs (Iexplore, Wmplayer, Wordpad) in the Start menu chooser.** In a new environment they are created
  while the installer runs, so they looked like "new" .exe files. Fixed: `detect.WINE_BUILTIN` filters them out
- [x] **"Previous versions" window: empty buttons, a window without a title.** Python cleaned up the translator object
  (`Cannot call method 't' of null` in the log). Fixed (`versions.py`): it stays in a variable
- [x] **Sloth Center → Programs → "Install a program…":** the browser did not open in the Downloads folder
  (`StandardPaths is not defined`). Fixed: `import QtCore` (`WinProgramsPage.qml`)
- [x] **Sloth Center → Games: the upscaling drop-down is empty.** `indexOfValue` ran before the model was loaded.
  Fixed (`GamesPage.qml`)
- [x] **File backup: "Back up now" asked for a password** in the "only for risky things" mode too. Decision (2026-10-20): it should
  not ask. Fixed: `sloth-helper-backup` (only `snapshot-now`), its own polkit action (`org.slothos.helper.backup`,
  `allow_active: yes`; like Windows' File History). Deleting and the settings still need a password
- [x] **Welcome after an interruption** continues where it was (2026-10-20): `welcome-progress.json` (step, language,
  chosen apps, appearance, password choice, the finished apps and the queue of Windows installers); interrupted while
  installing: at the last category, with the same choices (the installed ones are done at once); interrupted at the end:
  it offers the Windows installers again; deleted at the end. Tried offscreen (real controller, fake installer);
  on a real machine: a restart in the middle of Welcome after the reset
- [x] Welcome, sharing step: removed the stale "Windows programs" parenthetical; the page is called "Programs" now.
- [ ] System health, in a VM: "Machine Check Exception Logging Daemon" did not start (a VM has no MCE); check on a real
  machine whether it comes up; if only in a VM, do not report it in a VM

**Open bugs (small)**
- [x] Mute: it unmutes by itself (2026-10-20, based on a `pactl subscribe` + `alsactl monitor` log). Not the
  key: PipeWire's AirPlay discovery (`pipewire-config-raop`) added every Mac on the network as a sound output
  (school Wi-Fi, ~20 devices); on a Wi-Fi change and every few seconds afterwards new outputs came, and each of them
  lifted Plasma's "mute everything" state. Fixed: the package is removed from the image (`slim-image.sh`).
  Check on a real machine after the update: mute, Wi-Fi off and on, whether it stays muted
- [x] Installing the first .exe on a fresh system was "loading" for minutes (2026-10-20, real machine, after reinstalling). By
  default umu looks for the latest UMU-Proton and runtime on every start, and if the bundled one is not the latest,
  downloads them first. Fixed (`backend.local_runtime`, `runner.py`): in the foreground the latest Proton on the machine (or the bundled
  one) starts (`PROTONPATH`), the runtime is not updated (`UMU_RUNTIME_UPDATE=0`); updating stays in the background
  (sloth-windows-prepare). Check on a real machine
- [x] Sloth Center on the taskbar by default (next to Dolphin and Discover; for a new user and when changing the layout)
- [x] The taskbar balloon of Windows programs (e.g. Battle.net, EA app when minimized to the tray) came from the top left
  corner of the screen (2026-10-20, real machine). Wine puts the balloon in the middle of the tray icon's window; on Plasma these
  (invisible) windows are in the top left corner because of xembedsniproxy. Fixed: `sloth-wine-balloons.service`
  (`/usr/libexec/sloth-os/wine-balloons`, libX11 through ctypes, waits for events) moves the popups of Wine's explorer.exe that land there
  to the bottom right corner of the work area, above the tray icons. Tried on Xvfb; check on a real machine
- [x] Sloth Center, Updates: after a check / install, Sloth Center had to be reopened to see the new version
  or the pending restart (2026-10-20). It read the state from the D-Bus proxy's cache, which only updated
  late. Fixed: it always asks directly (`Properties.Get`), and looks again 2 and 8 s after an operation.
  Check on a real machine
- [x] Log noise: every 30 seconds "BAT0: chmod … charge_control_*_threshold failed". Universal Blue's
  `99-thinkpad-thresholds-udev.rules` did not check whether the file exists (an HP has none). Fixed (2026-10-20):
  a fixed rule of the same name in `/etc/udev/rules.d` (only if the file exists; it works the same on ThinkPads)
- [x] On a Hungarian system Sloth Center showed most texts in English ("Updates", "Open"): the translation catalog
  laid the English fallback over Hungarian too, and Sloth Center's hu.json only had a few lines (back then the
  Hungarian text itself was the key). Fixed (2026-10-20, `sloth_common/i18n.py`); since 2026-10-21 the keys are English
  and hu.json is a full translation
- [x] **Sloth Center, Updates: "up to date" although there is a new version** (2026-10-20, real machine): Sloth Center
  looked at the "ref-has-new-commit" field of rpm-ostree's CachedUpdate, which is always false for a container image; there
  "manifest-diff" (added / removed layers) shows the new version. Until then only the automatic background update
  brought the new one. Fixed (`updates.py`, `update_available`)
- [x] **rpm-ostree crash during an update** (2026-10-20, real machine: "Bus owner changed … daemon crashed", the
  download was interrupted; before it in the log "Forcibly closing transaction due to timeout", then a core dump in
  `deploy_transaction_execute`). Cause: Sloth Center did not close the connection at the end of the transaction (the command-line
  rpm-ostree does), the service forcibly closed it after 30 s, and a newer operation running then crashed. Fixed
  (`rpmostree.py`, `Transaction._close`): for the operations of Updates, Advanced settings, Drivers and the Developer panel
  too. Check on a real machine: after an update check there is no more "Forcibly closing" in the log
- [x] **A notification about an update prepared in the background** (2026-10-20, at the user's request): the automatic update
  quietly prepared the new version, and it looked as if the update came "only after a restart". Now a Plasma
  notification says so ("An update is ready … it installs at the next restart", with a "Restart now" button), once per
  version: `sloth-update-notify.path` (when `/run/ostree/staged-deployment` changes) and at login
  (`sloth_center/update_notify.py`). Tried with a fake rpm-ostree; check on a real machine that the path unit starts
- [x] Boot loop with an encrypted disk: it was a user error, not the system's (2026-10-20: tested again, it works)
- [x] Installer, account page: the password fields' placeholder is English ("Password"). It is Kirigami's own text and does
  not follow the installer's language change; emptied (the label is there), for the encryption password fields too (2026-10-20)
- [x] Welcome without internet: "Skip" did not move on. Not a bug: in the first (browser) step without a choice the
  "You did not choose a browser" question comes deliberately; in the VM fast repeated clicking opened and closed it
- [x] "Save log": the file name was Hungarian on an English system too. Now in the interface's language, ASCII letters only (2026-10-20)
- [x] **Battle.net: opens, closes after ~30 s (code 3)** (2026-10-20, based on the program's own logs):
  a 32-bit program, and there was not a single 32-bit library on the system (Fedora's wine-core is 64-bit only).
  The runtime passes the system's graphics driver to the program; for a 32-bit one there was nothing, so it got no
  Vulkan (`VK_KHR_surface` missing, DXVK: "Required instance extensions not supported"), the built-in
  browser engine's GPU process exited, and the program crashed. The runtime's 32-bit helper did not start either
  ("i386-linux-gnu-capsule-capture-libs … No such file": the file exists, `/lib/ld-linux.so.2` was missing).
  Fixed: `mesa-dri-drivers.i686`, `mesa-vulkan-drivers.i686` (gaming.yml; ~400 MB), on NVIDIA the driver's 32-bit
  part (`nvidia-32bit.sh`, check in the CI log). It probably affected the other 32-bit installers too.
  Also: the .exe handler does not remember a setting as "working" for a program exiting with an error code within 45 s.
  **Tried on a real machine (2026-10-20, ed2bd39 image): Battle.net starts, WoW Classic installs.** Still to check:
  starting the game from Battle.net
- [x] **EA app: solved** (2026-10-20, real machine: it installed and started on the 8th try). The installer copies the files
  into the `EA Desktop\EA Desktop` folder, then one of its own steps renames it to `EA Desktop\<version>\EA Desktop`,
  and asks for a link in the old place; Wine 10 does not create it, and the next step (starting the service) comes
  within milliseconds. Fix: `sloth_exe/stagedlinks.py` – while an EA installer or the EA app runs, it watches the folder
  with inotify, and right after the rename (~1 ms) puts a Linux link in its place (Wine follows it); before starting it
  points it at the latest version (the EA app's updates switch the same way). Test: `tools/tests/test_stagedlinks.py`.
  With Proton 11 (Wine ≥ 10.19, real links) the fix becomes unnecessary by itself, it does not get in the way.
  **In general, for every program** (2026-10-20 afternoon): Wine 10 writes every skipped link request into the log
  (`fixme:file:CreateSymbolicLinkW (L"<link>" L"<target>" …): stub`); the .exe handler used to silence it (`fixme-all`),
  now it turns the `file` channel back on, and creates the link by reading the line (`stagedlinks.from_log_line`: only
  inside the program's environment, never overwriting an existing file, with Windows-style case handling). Through the log
  this arrives a few milliseconds later than the watcher that worked for EA, so EA keeps its own; for the other programs it is enough
  **Still to check:** through the .exe handler (Welcome / double-click), installing and starting a game, the EA app's update
- [ ] **EA app – the investigation** (2026-10-20 morning, real machine, with umu-run, with detailed logs):
  - INST-14-1627: at the end the MSI cannot start `EABackgroundService` (`service_start returning 2`, the
    file is not under `…\EA Desktop\EA Desktop\`). Cause: the EA app installs with **symbolic links**
    (`EAX_DISABLE_SYMLINKS="0"`; the files into a versioned folder, `EA Desktop\EA Desktop` is only a link), and the link is
    not created under Wine. Lutris' ea-app-standard recipe works around this too (it takes the error code as success, then
    moves the versioned folder into place)
  - `EAX_DISABLE_SYMLINKS=1` on the installer's command line: the installer accepts it, then **sets it back to 0 itself**
  - The MSI can be extracted: `EAappInstaller.exe -layout C:\eamsi -quiet` (got it: EAapp-13.809.0.6322-16067214.msi).
    Directly (msiexec, from a .bat file, with all of the installer's parameters, `EAX_DISABLE_SYMLINKS=1`): the file copy
    starts, but one of EA's own steps (CustomActionData: InstallAction=Install…) stops with 1603
  - GE-Proton11-11 (`PROTONPATH=GE-Proton`), the original installer: it stops right at the start, at `JunoInitializeSession` (a .NET step),
    with 1603; before that `mscoree … installroot`: the environment has no wine-mono
  - **The cause** (2026-10-20, looked into): UMU-Proton-10.0-4 is built on Wine 10.0, where `CreateSymbolicLinkW` is only a
    stub: it reports success but creates no link (the same symptom with the EA app's updates: thewaryfox.com,
    2026-02-08). Wine has link support since 10.19 (reparse points); Valve's Proton 11.0-2e (2026-10-09) explicitly
    brings EA app fixes too. There is no UMU-Proton 11 yet (the latest: 10.0-4), there is GE-Proton11 (see above, the .NET step)
  - **Two ways:** (A) filling in the missing link on our side, independent of Proton: during the install a watcher
    puts a Linux link to the versioned folder in place of `EA Desktop\EA Desktop` (Wine follows it), and before starting we
    always point it at the latest version (because of the EA app's updates). Test: `ea-proba7.sh` (2026-10-20).
    (B) Proton 11, once there is a UMU-Proton 11, or GE-Proton11's .NET problem is solved
  - Earlier ideas: (1) Lutris' way: accept the installer's error, and put the versioned folder in place (for this one
    needs to know where the files are before the rollback: stop it before the rollback, or save them after the file
    copy); (2) GE-Proton 11 with wine-mono (`winetricks`/`mono` into the environment), because links may work there;
    (3) the `CustomActionData` step's own log (EA ProgramData/Logs)
- [x] **Epic:** the new installer (EpicInstaller-20.3.3.exe, from the website) fails its own signature check under Wine
  ("Certificate CN does not match 'Epic Games Inc.'"). Decision (2026-10-20): Heroic instead of Epic and GOG. The two
  Windows launchers were removed from Welcome, Heroic's description says why we recommend it; whoever opens the Windows
  installer anyway gets Heroic recommended by the .exe handler too (below)
- [x] **Teams (MSTeamsSetup.exe):** a .NET installer, it crashes under Wine (Mono); the new Teams does not run under Wine
  anyway. Fixed (2026-10-20): the .exe handler recognizes popular installers that have a Linux version
  (`sloth_common/apps/native.py`, ~40 programs, a local list, works without internet too), and recommends that from Discover; the
  Windows install stays available next to it. Three kinds of text: "fits better" (e.g. Discord, Chrome),
  "the Windows one does not work reliably here" (Teams, Steam), and Epic/GOG -> Heroic, with the reason
- [ ] EA app, Ubisoft Connect: whether they need `LAUNCHER_STUBS` (the test decides)
- [x] `tools/tests/test_apps.py`: 4 tests failed: /tmp is tmpfs here, where the library rightly does not allow Windows programs;
  the test's temporary folder is on disk now (`~/.cache`), all 30 pass (2026-10-20)

**Later**
- [ ] (After 1.0; decision: 2026-10-20) Child account and parental controls. Survey (2026-10-20), about 3–4 times the work of today's file backup:
  1. Creating a child account (not an administrator) from Sloth Center: small
  2. Restricting apps: malcontent 0.14 (it is in Fedora 44) – filtering by age rating, forbidding installs,
     forbidding single apps; Flatpak (and so Welcome) respects it, Discover to be checked. Our own interface in Sloth
     Center (malcontent-control is GNOME's): medium
  3. Screen time and bedtime: malcontent only keeps records, enforcement is in GNOME, there is none on KDE;
     we need our own (warning notifications, locking / signing out at the end, signing in only in the allowed
     time): bigger
  4. Web filtering: a family-friendly DNS only for the child's account (or malcontent's NSS module), turning off the browsers'
     own DNS (DoH) with a policy: medium, a lot of testing
  Suggested order: 1+2+3 in one round, web filtering separately
  Until then a "Coming soon" menu item shows it in Sloth Center (Parental controls, 2026-10-20)
- [ ] Our own Flatpak repository for the apps from GitHub (e.g. ArtCraft), so Discover updates them
- [x] Not needed (2026-10-27, measured on the laptop: `btrfs filesystem du` shows 0 B exclusive for
  `compatibilitytools.d`, so the `--reflink=auto` copy already shares its blocks with the image's copy; a link
  would also break Proton, which writes `dist.lock` and `default_pfx` into its own folder, and a newer bundled
  Proton would remove the old one under programs pinned to it).
  A link instead of the duplicated copy of Proton (about 1.4 GB on disk). Plan (2026-10-20): first check on the machine
  whether it really takes space (`windows-runtime-seed` already copies with `--reflink=auto`); if so, a link to the bundled
  copy instead of the Proton folder (Proton does not write into its own folder), the runtime (Steam Linux Runtime)
  stays a copy, because umu updates it in place. Small work
- [x] **Feedback from Sloth Center** (2026-10-20, at the user's request). **Live (2026-10-20 evening):**
  - [x] Worker: `POST /v1/feedback` (a GitHub issue with the `feedback` + kind labels, the text in a code block, 5 a day per address)
    and `GET /v1/feedback/log/<id>` (the log only with `LOG_TOKEN`, for 30 days, the `feedback_logs` table). Tried with a fake D1
    and GitHub, then live too (test issue #1: labels, the log 401 without the token, readable with it)
  - [x] Sloth Center: a "Feedback" page under System health (`feedback.py`, `FeedbackPage.qml`; the log from
    `health.write_log`, its end, max. 500 KB). Works on a real machine (#5)
  - [x] Repository: the public `Sloth-OS-Linux/feedback` (English README), labels: `feedback`, `bug`, `idea`, `other`
  - [x] Going live: the `feedback_logs` table (with `--command`; the `--file` import gives a permission error with the OAuth token),
    `GITHUB_TOKEN` (fine-grained, only writing Issues of the feedback repository; **replace it before it expires**), `LOG_TOKEN` (on the
    machine: `/mnt/adatok/sloth-dev/feedback-log-token`), `FEEDBACK_REPO` in `wrangler.toml`, `wrangler deploy`
  - [x] Translation into all 50 languages (2026-10-20; the other languages are machine quality, also for the native review)
  - [x] The website's FAQ: Sloth Center → Feedback
  - Reviewing together here: `gh issue list -R Sloth-OS-Linux/feedback -l feedback`; the log:
    `curl -H "Authorization: Bearer $(cat /mnt/adatok/sloth-dev/feedback-log-token)" <link>`
- [x] **A verified update indicator** (2026-10-22): on Sloth Center's Updates
  page a green tick, "Verified updates ✓ – the system only accepts updates signed by Sloth OS"
  (`ostree-image-signed` in the running version's origin); if it is not turned on, a warning
- [ ] Work account: Entra ID; opening the password store (KWallet) with a PIN / fingerprint (details below, Sign-in)
- [ ] Bringing Steam games into self-healing and the shared knowledge
- [x] Reset from the boot menu (below, item 8)
- [ ] (After 1.0; decision: 2026-10-20) Windows programs in Discover (details below)

### Important: the test of 2026-10-16 still ran with the old image
The tested ISO (`out/sloth-os.iso`) was made on 2026-10-16 at 08:17, when the registry's `latest` tag still pointed to the
image of 2026-10-15 22:31 (`35e4c9d`). The fixes of 10-16 (below) only got into `latest` at 11:33;
that is why "Sloth OS 44" still showed, and why Battle.net behaved the old way. **A new ISO
only after pushing the current work and the CI build.** The version running on the installed machine: Sloth Center →
System health → Save log (its start now shows the running image too).

### Done 2026-10-19: unified Windows app management (the requests of the 2026-10-16 evening test)
Tried with unit tests (`tools/tests/test_apps.py`, on Linux, without Qt and Wine) and by loading the Qt modules,
**not yet on a real machine**.
- **A shared application library** (`sloth_common/apps/`: library, menu, winreg, detect, steam): the .exe handler and
  Sloth Center use the same (the earlier double folder reading is gone)
- **A visible place: `~/Applications/<program>/`**: `windows/` (the program's Windows environment), `.sloth/app.json`
  (data), a "Program files" link to the installed files, the folder's icon in Dolphin. The place can be set in Sloth
  Center (only a Linux file system; a clear message for NTFS/exFAT/FAT), the programs
  can be moved (the Start menu entries stay valid). From the old place
  (`~/.local/share/sloth-os/windows-programs`) they move over once, with a rename (running programs stay)
- **Recognition after installing:** from the registry's "Uninstall" entry the real name ("Battle.net"), publisher,
  version, install location; the launcher from the shortcuts, the registry's icon or scored .exe files (the
  updaters, crash reporters, uninstallers drop out; the same name only once). The install is only done when nothing
  runs in the program's environment any more. If it is not certain: a "Another file…" browser. At the end "Start"
- **An already running program:** does not start again ("X is already running"); if something else runs in its environment (e.g. the launcher, and the user
  starts a game), it joins that (`runinprefix`), it does not wait until it ends
- **Sloth Center → Windows programs:** Start, Files, Start menu, Repair (deleting the remembered start
  settings), Reinstall, Move, "Install a program…", the programs' location
- **Steam takeover:** adding the Windows programs added to Steam by hand (`shortcuts.vdf`) without
  reinstalling: "Through Steam" (only an entry, Steam starts it) or "Take over" (a reflink copy of Steam's
  environment, Sloth starts it from there). Neither touches Steam's files; we never start Steam's environment
  with our own runner
- **Dolphin 128 TB:** the loop device of composefs (the system's read-only image, since Fedora 42) showed as a nameless
  volume; a udev rule hides it (`/usr/lib/udev/rules.d/90-sloth-udisks.rules`), the
  system partition's name is "Sloth OS". Display only, mounts are not touched. Check on a real machine
- **Save log** (System health): at its start the running image, the disks, the mounts and the loop devices
- **Epic:** the 64-bit client starts instead of the 32-bit launcher (as in Lutris)
- **Translations:** the new texts in all 50 languages

### Done 2026-10-16 (the morning test's bugs, details below, "The morning test's result")
Everything pushed; tried with simulation / unit tests, **not yet on a real machine** (the 10-16 ISO did not have them
yet, see above).
- **Welcome:** the apps install one by one, in order, with the total download size; a Restart button at the end;
  refreshing the taskbar icons on closing
- **.exe handler:** installs a program only once (Open / Reinstall); Battle.net starts with the client
  (until now the client closed too when the launcher exited)
- **Steam's first start:** a Plasma notification while Steam downloads itself
- **Version number:** "Sloth OS 1.0 (Fedora Atomic 44)"

### Next test (a new ISO after the CI build of the 2026-10-19 changes)
- [x] **Welcome:** 4–5 apps at once: they install in order, one by one; the label is only "Installing X…" and the progress bar
  (without the size since 2026-10-19, at the user's request); no double row; Restart at the end, then the icons on the taskbar; whether the icons are right without Restart too
- [x] **Steam:** whether the notification comes on the first start ("Steam's first start", "x MB downloaded"), whether it disappears when
  Steam opens; then `bootstrap_log.txt`. 2026-10-19: it works, it shows it right
- [ ] **Battle.net:** install, start from the Start menu; whether it stays open; signing in, installing and
  starting a game; only one entry in the Start menu
- [x] **.exe handler:** opening the same installer again says "already installed", Open starts it
- [x] **Application library:** after installing, Battle.net is in the `~/Applications/Battle.net/` folder (in Dolphin
  with the program's icon, with "Program files" in it); its name is "Battle.net" (not "Battle Net"); on the choice list one
  entry is ticked; the "Start" button starts it. An installer that exits as a downloader (e.g. Battle.net,
  EA app): the .exe handler waits for the actual install. The background log: `~/.cache/sloth-os/apps/<program>/naplo/`
- [ ] **An already running program:** starting it again from the Start menu while Battle.net runs says "already running"; starting a game
  from Battle.net (and from the Start menu, if there is an entry) while Battle.net runs
- [x] **Sloth Center → Windows programs:** Start, Files, Start menu, Repair, Move (to another folder,
  whether it starts from the Start menu afterwards), changing the location to an NTFS USB stick (a clear message), Remove
- [ ] **Steam takeover:** a Battle.net added to Steam by hand appears among "Programs added to Steam";
  both "Through Steam" and "Take over"; afterwards it starts from Steam the same way too
- [ ] **Migration:** a program in the old place (`~/.local/share/sloth-os/windows-programs`) is under
  `~/Applications` after the update, and starts from the Start menu
- [x] **Dolphin:** there is no nameless 128 TB drive among the Devices; the system partition's name is "Sloth OS"
- [x] **Save log** (System health): its start shows the running image and the disks
- [x] **System information:** "Sloth OS 1.0 (Fedora Atomic 44)"
- [ ] **Open questions for the test of the 2026-10-19 ISO** (answers here; tick what is fine). Fine so far: fingerprint,
  PIN, the encrypted disk's padlock password prompt (the dots fixed):
  - [ ] Compressed memory reserve (Advanced settings): after changing it and restarting, does it show the new size?
    (not tested yet)
  - [x] Does the PIN work on the lock screen (Win+L) too, not only at login? Yes, everywhere
  - [x] System information: does "Sloth OS 1.0 (Fedora Atomic 44)" show? "Sloth OS 44" was on Sloth Center's Updates
    page ("Current version"): it was made from rpm-ostree's version label ("44.2026…"). Fixed: from the system version's
    own os-release (PRETTY_NAME); for an update not downloaded yet "Sloth OS" + date
  - [x] Welcome, several apps at once: do they install in order, one by one? Yes; Vivaldi installed too. The
    Restart button at the end works
  - [x] System update: has there been one? Was everything fine on the Updates page? Yes, fine
  - [ ] Battle.net again, after the background preparation: does its own installer come up (see the bugs below); because
    of the boot loop (below) it did not get this far yet
- [ ] The rest of the morning test: encryption, updates with signature verification, an NVIDIA machine, next to Windows (needs a tester)
- [x] Watching the still open bugs (2026-10-20: all solved): muting (which button: key / tray icon; when does it come back: by itself, on a
  notification's sound, on changing the volume, at login?), Discover updating the fresh apps (what did it update:
  the app itself or an extension, e.g. `GL.default`?), Vivaldi from Welcome (the error message in the saved log)

### Done 2026-10-15 afternoon and night (details at the phases)
Everything pushed; most of it is only tried with simulation and on a loop device, **not yet on a real machine / in a VM**.
- **The bugs of the first real-machine test fixed:** the live system's language after "Try", Welcome's status texts,
  icons after installing, Battle.net (see below, "Earlier (2026-10-15)")
- **A self-healing runner for Windows programs** (phase 2): recognition (umu database, Steam AppID), recipes (Battle.net,
  Ubisoft Connect, Epic, GOG Galaxy), diagnosis from the background log (missing DLL → component, Vulkan error → WineD3D…),
  self-healing with other settings and Proton versions (with a Btrfs snapshot), rollback after a Proton update
- **Shared knowledge** (phase 2): Cloudflare Worker + D1 (`sloth-os-knowledge.slothos.workers.dev`), the public
  `Sloth-OS-Linux/sloth-os-knowledge` repository (hourly export, a monthly ProtonDB base: 287 games, daily watching);
  sharing only with permission (a new step in Welcome, a switch in Sloth Center); described in the README
- **Installer** (phase 4): installing next to Windows (shrinking or free space, recognizing BitLocker / fast startup / BIOS,
  a visible boot menu with Windows, a local-time clock), disk encryption (LUKS2, separate /boot, a password prompt with the
  chosen layout and a padlock icon)
- **Installed system:** the automatic NVIDIA version (in the background, with a notification, with a Secure Boot key), signed
  updates (both variants' signatures accepted, switching older installs once), protecting the boot order
  next to Windows, notifications in the top right corner, `sloth-center --page <page>`
- **Translations:** every new text in all 50 languages (Welcome, installer, Sloth Center)

### Morning test (a new ISO after today's CI build)
On a real machine and/or in a VM; whatever does not work comes back here as a bug.
- [x] **Live system:** after choosing a language, "Try" → the desktop comes up in the chosen language; notifications at the top right
- [x] **Installer, whole disk:** a plain install; then the same **with encryption** (a padlock icon at boot, the password works with the
  chosen layout, e.g. "z"/"y" for Hungarian; after a wrong password it asks again)
- [ ] **Installer, next to Windows** (in a VM with a Windows disk or an NTFS + EFI test disk): the survey and
  the slider, the explanations (e.g. hibernated Windows), the install, the Windows entry in the boot menu, Windows
  still starts afterwards, the clock is right in both systems
- [x] **First start:** quiet boot, hidden GRUB (a visible menu next to Windows), the account from the installer, Welcome
- [x] **Welcome:** the new "Sharing experiences" step (yes / no, Next only after a choice), installing the apps
  (what it downloads / installs, "x / y MB"), the icons show right away, Steam on the taskbar with its icon
- [x] **.exe handler:** installing Battle.net and starting it from the Start menu (whether it keeps running), a simple .exe, a game;
  the background log (since 2026-10-19 `~/.cache/sloth-os/apps/<program>/naplo/`) and the remembered setting
  (`~/Applications/<program>/.sloth/app.json`)
- [x] **Sloth Center:** the Windows programs page (sharing switch), the Drivers page, looking through the other pages
- [ ] **Updates:** whether a system update goes through with signature verification (`rpm-ostree status`: `ostree-image-signed`);
  whether the old install on the test laptop switches by itself (`sloth-signed-updates`)
- [ ] **On an NVIDIA machine** (if one is at hand): it downloads the NVIDIA version by itself, notifies, and that runs after a restart
- [x] Where the names "Fedora" or "Universal Blue" still show (login screen, Discover, System Settings)

### The morning test's result (2026-10-16, real machine, USB stick, whole disk, without encryption)
Fine: the live system and its language, a plain install, quiet boot, hidden GRUB, login, Sloth Center.
Still to do: encryption, next to Windows (needs a tester, there is no Windows machine), an NVIDIA machine.
Bugs found (we fix them one by one):
- [x] **Welcome, installing apps (big bug):** the process shows the apps all over the place. The same app (e.g.
  Steam) appears several times, sometimes with the same size, and one cannot tell whether only the display is wrong, or
  it really downloads it several times. Request: install from top to bottom, one by one. Downloading may go in parallel,
  but the text only says "Installing …", it should not mention the download. Fixed (tried with simulation,
  still to test on a real machine): the cause was a single shared transaction (every extension showed with the app's name);
  now a separate transaction per app, a size survey before it, the label "Installing X…", below it "330 MB / 430 MB"
- [x] **The end of Welcome:** there should be a restart button, so everything loads properly. Done (test on a real machine):
  if an app was installed, Restart is the main button with a short explanation; "Let the fun begin!" stays too
- [x] After closing Welcome, the taskbar still shows the generic icons instead of the apps' icons (fine after a restart).
  Fixed (test on a real machine): before pinning to the taskbar, `kbuildsycoca6` and an icon reload signal
  (`/KIconLoader iconChanged`); if that is not enough either, the Restart button solves it
- [x] **.exe handler (big bug):** it lets the same program be installed twice (or more), and it appears in the Start
  menu several times too. Fixed (still to test on a real machine): if the program already exists (the same name
  or the same installer file), "X is already installed.", Open (by default) or Reinstall into the same
  folder; no new folder (`-2`, `-3`) and no new Start menu entry is made. The old duplicates stay, they can be deleted by hand
- [x] Battle.net still does not start, it behaves the same as before. No data arrived in the shared knowledge
  (no export in the `sloth-os-knowledge` repository until the morning of 2026-10-16), check whether the system sends reports.
  The likely cause is found and fixed (test on a real machine): Proton's `waitforexitandrun` mode waits for the previous
  session before starting, not for the child processes, and umu also only waits for the started process.
  "Battle.net Launcher.exe" starts the client and exits; then the runner stops, and the client's window
  disappears too (from Steam it worked because Steam waits for every process). Now the client (`Battle.net.exe`)
  starts directly (`quirks.launch_target`, like Lutris' Blizzard recipes); the self-healing data belongs to the
  client, so the old, mistaken "does not work" entries do not count
- [x] .exe handler: if a program already runs and the user starts it again, because of `waitforexitandrun` the new start
  waits until the previous session ends ("Starting…"). Fixed (2026-10-19, test on a real machine): if the same
  program runs, "X is already running"; if something else runs in its environment, it joins that (`runinprefix`)
- [ ] Check whether the other launchers (EA app, Ubisoft Connect, Epic, GOG Galaxy) also hand over to another
  process; if so, `quirks.LAUNCHER_STUBS`. Done for Epic (2026-10-19: the 64-bit client instead of the 32-bit
  launcher, as in Lutris); the EA app (`EALauncher.exe`) and Ubisoft Connect (`UbisoftConnect.exe`) run with the launcher in Lutris
  too, for these the test decides
- [x] Steam (Flatpak) did not open: it loaded for about 10 s, then nothing. Later it started after all, just when
  the user added the "Battle net" entry instead of Battle.net to the Start menu in Sloth Center (it may be
  a coincidence, but it took very long). Likely cause: on its first start Steam downloads its own client
  without a window. Now a Plasma notification says so ("Steam's first start", "x MB downloaded") if Steam does not
  open within 15 s, and the notification disappears when Steam's window appears
  (`sloth_center/steam_first_run.py`, `sloth-steam-first-run.path`). Test on a real machine, and check
  `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/logs/bootstrap_log.txt` to see whether this really was the cause
- [x] (2026-10-20: not caused by encryption, solved) Installed with an encrypted disk, the machine sat on the logo for half an hour (report of 2026-10-19). The image's initramfs is
  fine (crypt, systemd-cryptsetup, the Plymouth password prompt, lock.png, layouts); waiting forever on the logo
  points to the password prompt (systemd waits for the password without a timeout), the small padlock probably went unnoticed or was not
  visible. Fixed: a bigger padlock and an input line. At the next test: whether it shows, and what Esc shows
- [x] On the encrypted disk's password prompt squares showed in place of the typed characters (the initramfs font has no "●").
  Fixed (2026-10-19): the dots come from an image (dot.png), not from text
- [ ] Installing Battle.net after a fresh (encrypted) install: "Preparing the Battle.net installation…" for 20 minutes, the
  Battle.net installer itself did not come up (test of 2026-10-19). Likely cause: the background preparation starting 3 minutes
  after login (`sloth-windows-prepare`, downloading Proton and the runtime) ran with the "idle" disk priority,
  which almost stops next to other disk work (installing apps, encryption), and umu quietly waited for it.
  Fixed: the .exe handler takes it over at the start (stops the one running in the background, and continues in the foreground,
  with visible progress), in the background "best-effort" priority 7; after 60 s of silence a "Still working…" text. Watch
  at the next test; if it happens again: Save log (with the `sloth-windows-prepare` log in it)
- [x] (2026-10-20: it was a user error, tested again, it works) **Starting with an encrypted disk: after the password the machine restarts** (2026-10-19 evening, on a machine installed
  from the afternoon ISO, not on the first start). The padlock password prompt appears, after typing the password the machine's
  (BIOS) logo comes again, then the password prompt again. The user reinstalls. Questions: does it start with the previous
  entry in the GRUB menu (Esc at boot); was there a system update or an NVIDIA switch before (a change that takes
  effect after a restart); does the GRUB menu appear by itself after the failed start. According to the user there
  was a change "effective after a restart / login" before, they do not remember which; they did not change anything in
  the Advanced settings. Reinstall from a fresh ISO.
  VM test (2026-10-19 evening, the 20:30 ISO, Hungarian layout, encryption): install, first start (padlock, dots,
  login screen), automatic login in Welcome, Restart, password: straight to the desktop. The boot loop
  did not come up; the VM has no NVIDIA and there was no system update, watch these on the real machine
- [x] **Installer: a black screen at the end instead of the "Restart" page** (VM test 2026-10-19). The install
  went through, but when deleting the work partition (`finish_partitions`) systemd stopped `var-tmp.mount`, and with it
  `basic.target` (RequiresMountsFor=/var/tmp) and the live desktop, installer included. Cause: the work partition was
  bind-mounted over /var/tmp, so var-tmp.mount was bound to the partition. Fixed: it is mounted as an overlay
  (according to systemd the source is "overlay", not the partition; tried in a VM), needs a new ISO. With the 20:30 ISO
  the install is fine too: if the screen goes dark after 90%, after waiting 2 minutes the power button restarts it
- [x] Installer, account page: the password fields' placeholder is English ("Password"); fixed 2026-10-20 (see above)
- [x] **The update failed with "Something went wrong"** (2026-10-19 evening, on the HP, even after two restarts): on a new
  push CI cancelled the running build, which by then had already pushed `latest`, but could not sign it;
  the machines updating with signature verification reject the unsigned `latest`. Fixed: on the main branch a running build
  is not cancelled (`cancel-in-progress` only for PRs); Sloth Center shows a clear message for this error
  ("The latest update is not available yet…")
- [x] **.exe handler: not a single Windows program install started** (2026-10-19 evening, real machine, unencrypted
  install): "Still working…" spun for half an hour. According to the log Proton and the runtime were downloaded within
  1 minute; when starting the install `AttributeError: 'App' object has no attribute 'slug'` (runner.py, a leftover of the
  morning's application library rework, `program.id` instead of `program.slug`). Fixed, and any unexpected error
  while starting the runner now shows an error page instead of spinning on. Smoke test with Qt
- [x] .exe handler: an unfinished install (the installer did not run to the end, only the folder and the recipe's setting were
  created) was "already installed", Open started nothing. Now only a finished install counts (a Start menu entry
  or the recognition's data); the new install goes into the unfinished folder, no duplicate
- [x] Sloth Center's "Save log" file name is Hungarian (`sloth-os-naplo.txt`), on an English system too; fixed 2026-10-20 (see above)
- [x] `tools/tests/test_apps.py`: 4 tests fail on this machine (before the 2026-10-19 fix too), check it; fixed 2026-10-20 (see above)
- [x] **Proton and Steam Runtime in the image from the factory** (2026-10-19, the user's request): UMU-Proton-10.0-4 and
  the Steam Linux Runtime (sniper 3.0.20261007.263965) pinned, with checksums (`files/scripts/windows-runtime.sh`,
  `/usr/share/sloth-os/windows-runtime`, 2.2 GB unpacked). On first use `windows-runtime-seed` copies them into the
  user's folder (the .exe handler's "Preparing the first start…" step and sloth-windows-prepare),
  afterwards umu starts without internet too, and updates in the background. Tried locally (copying, pv-verify: OK);
  test on a real machine: a fresh install, an .exe without internet. The ISO's size: at the end with squashing
  (`SLOTH_SQUASH=1`) and, if needed, reduce it otherwise
  - [ ] Later: a factory template environment with the most common components (e.g. vcrun2022), if the tests say it is needed
- [x] Welcome without internet: "Skip" does not move on on the app pages (VM, 2026-10-19); not a bug (see above)
- [x] The mute button mutes, but it does not stay that way: the volume comes back to the previous one, something overrides it. 2026-10-19:
  it came up again; muting lifts almost immediately as soon as any button is pressed (keyboard).
  The cause was AirPlay discovery (see above, "Open bugs", 2026-10-20)
- [x] **Dolphin, Devices: the nameless 128 TB drive** (2026-10-19 evening, based on the user's pictures and the saved
  log): not a loop device (the machine has none), but the system's root itself, the composefs overlay mounted on /.
  Of the overlay mounts KDE Solid deliberately shows the one mounted on / (for live systems), and it can only be hidden with the
  `x-gvfs-hide` option in /etc/fstab (there is no upstream fix). Fixed:
  `sloth-hide-root-overlay.service` adds the line `composefs / overlay ro,noauto,x-gvfs-hide 0 0` (on existing
  machines too). Tried in a VM: `StorageAccess.ignored = true`, after a restart systemd-remount-fs is fine.
  The 128 TiB is the recursive size in "Properties", including the virtual size of /proc/kcore. Besides, the system partition
  showed under the name "root" (Dolphin shows the file system's label, the udev name has no effect): the new installer gives it a
  "Sloth OS" label; on earlier installs "root" stays
- [x] **Reporting a successful start did not work on an encrypted disk** (VM, 2026-10-19): `boot-env` took the parent of the
  /dev/mapper/… root (the partition) as the disk, "No EFI partition.", sloth-boot-ok.service
  failed, so the boot menu would have come up on every start. Fixed: the disk from the chain of ancestors (`lsblk -s`)
- [x] Dolphin, Devices: the SSD's size shows as 128 TB. First fix (2026-10-19, not enough, see above): the
  nameless entry was the loop device of composefs (the read-only system image since Fedora 42); the 128 TB
  is probably the virtual size of /proc/kcore in the root's size calculation. A udev rule hides it
  (`90-sloth-udisks.rules`), the system partition's name is "Sloth OS". If it still shows at the test: Save log, at its
  start the disks and the loop devices
- [x] (2026-10-20: it was a faulty base package update, solved) Discover also updated the apps just installed from Welcome (e.g. Steam) (check why).
  Likely cause (2026-10-19): the base image's automatic app updater (`flatpak-system-update.timer`, 2 minutes after
  power-on) ran during Welcome. Now it is skipped while Welcome runs; watch at the test.
  Test of 2026-10-19: according to the user it only updated some Fedora base package (probably a
  Flatpak runtime, e.g. the Fedora Platform or `GL.default`), not the apps; so it is fine
- [x] The system's name is "Sloth OS 44" (Fedora's version number shows): Sloth OS should get its own version number (e.g. 1),
  and somewhere (e.g. in System information) it should show that it is based on Fedora Atomic. Done (check on a real
  machine): "Sloth OS 1.0 (Fedora Atomic 44)" (`branding.sh`: VERSION, PRETTY_NAME; VERSION_ID stays 44;
  `/etc/xdg/kcm-about-distrorc`: UseOSReleaseVersion)

### To do, in order of importance
**Required before publishing:**
1. [x] **The test above to the end, and fixing the bugs found.** There are many big new features that we only tried with
   simulation; before publishing all of them must work on a real machine. Still open from the morning test's bugs
   (in order): muting (the volume comes back; our code does not touch the volume, it must be observed on a real machine),
   Discover updating fresh apps, checking the other launchers (`LAUNCHER_STUBS`). Dolphin 128 TB and
   restarting a running program fixed (2026-10-19), check at the test. (2026-10-21: the real-machine test passed)
2. [ ] **Old (BIOS-only) machines** (after 1.0; decision: 2026-10-20, 1.0 is UEFI only)**:** whether the USB stick starts in BIOS mode, installing on a BIOS machine (the whole-disk
   install already has the BIOS boot partition); next to Windows on BIOS may stay with a "not supported" explanation
3. [x] **Making the repository public** and turning the daily automatic build back on (`.github/workflows/build.yml`), done
   2026-10-21. It is what lets installed machines get updates without signing in (once the ghcr.io packages are public too),
   and lets the installer check that updates are available without `--skip-fetch-check`.
   - [x] Secrets and personal data in the repository's whole history (2026-10-19): gitleaks (113 commits, all branches):
     no hits; manual search (e-mail, name, machine name, own paths, IP addresses, keys): every commit with the GitHub
     noreply address; `deploy-vm.sh` (`0fede6b`) only contains a VM-internal address (`10.0.2.100`);
     `SB_PASSWORD = "universalblue"` is Universal Blue's public Secure Boot password. The pictures have no personal
     metadata; the C2PA marking of `docs/branding/logo-source.png` only says that it was made with AI. 2026-10-21: the
     46 commits since then checked again, nothing
4. [x] **ISO hosting and download:** GitHub releases accept at most 2 GB per file, the ISO is 6.2 GB; done on
   SourceForge (free, with mirrors), with an SHA-256 checksum (2026-10-21)
5. [x] **Website and documentation:** download, writing the USB stick (from Windows too, with a GUI), first steps, FAQ
   (next to Windows, encryption, NVIDIA, privacy). Done (2026-10-19): the `codex/website-docs` start
   reviewed and fixed (home page, first steps, Windows programs, privacy, FAQ; the real
   logo, licenses and ODbL in the footer). 2026-10-21: the download page (SourceForge, system requirements, Fedora Media Writer /
   Rufus, boot menu keys, checksum, licenses) and the release texts are live on sloth-os-linux.github.io; the repository's
   stale `website/` copy was removed (the site lives in `Sloth-OS-Linux/sloth-os-linux.github.io`)
6. [x] **Licenses and names:** done (2026-10-19): the code is Apache-2.0 (`LICENSE`, like Universal Blue and BlueBuild),
   our own artwork (logo, wallpapers, boot animation) CC BY-SA 4.0, the app icons of Welcome belong to their vendors (`NOTICE`;
   in the image `/usr/share/licenses/sloth-os/`, in the wallpapers' data too). The ODbL marking of the ProtonDB data
   is on the download page (2026-10-21).
   - [x] The name "Sloth OS" (2026-10-19, not a legal opinion): there is no operating system with this name (there is a browser-based
     student joke project on GitHub); in the US a "SLOTH" trademark in class 9 for a "slow TV" player app
     (USPTO 6130782), another product area. EUIPO's machine search did not work: check by hand in TMview and
     at SZTNH too, or ask a trademark lawyer
7. [ ] **Native-speaker review of the translations** at least for the most common languages (English, German, Spanish, French…);
   the rest may stay machine-made, marked (decision 2026-10-21: it will come through feedback)

8. [ ] **Basics missing for people coming from Windows** (2026-10-19, agreed with the user; the size of the work still to
   agree):
   - [x] **Backing up and restoring your own files:** automatic Btrfs snapshots of home (hourly / daily,
     the old ones are deleted by themselves), right-click → "Previous versions" in Dolphin (as in Windows), a switch in Sloth
     Center for backing up to an external disk and for restoring
     - [x] **Snapshots** (2026-10-20): the installer does not create subvolumes, so at startup, before login,
       `/var/home` becomes a separate subvolume (`sloth-home-layout.service`, `home-snapshots layout`: a reflinked
       copy, an `mv --exchange` swap, the old one is deleted only afterwards; after an interruption it continues at the next
       start). The big, re-downloadable folders (`~/.cache`, the Flatpak apps' `cache` folders, Steam's `steamapps`,
       `~/Games`) are separate subvolumes too, so they stay out. An hourly snapshot (`sloth-home-snapshot.timer`) under
       `/var/home/.snapshots/<UTC time>`; keeping: every hour of the last day, then one a day (for at most 14
       days), then one a week, 2 weeks / 1 month (default) / 3 months. If the free space drops below 10% (but at least 3 GB),
       the oldest are deleted (the newest stays), and no new one is made
     - [x] **Previous versions** (Dolphin, right-click on a file, a folder or a folder's empty area; `sloth-versions`):
       for a file only the different versions, marked "Same as the current one"; Open (read-only),
       Restore (the current one to the Trash), Save as a copy (with the date in its name), for a folder "Bring back deleted
       items" (the existing ones are not touched) and the number of items deleted since
     - [x] **Sloth Center → File backup:** on/off, keep time, "Back up now", the list of saved states (Open
       in Dolphin), deleting them all. The operations that ask for a password go through sloth-helper
     - Test: `tools/tests/test_snapshots.py` (on a real Btrfs loop device, in the Sloth OS image; 9 tests), the two
       interfaces with offscreen screenshots. **Not yet on a real machine:** the first-start conversion with an existing,
       big home folder (how long it takes), SELinux labels afterwards, the Dolphin menu item, the Trash
     - [x] **Backup to an external disk** (2026-10-20): Pika Backup (Flathub), with a card on the File backup page: what it does,
       three steps to set it up, Install (in Discover; the card notices by itself when it is done) / Open
   - [x] **Resetting the computer** ("Reset this PC", 2026-10-20; tested on a real machine on 2026-10-21):
     Sloth Center → Reset this PC, with two modes; for both it lists what stays and what is deleted, and
     asks for confirmation. `files/system/usr/libexec/sloth-os/factory-reset`, in two steps:
     - now (sloth-helper `factory-reset`, with progress): downloading the latest version, removing the system packages
       added by hand (`rpm-ostree reset`) and kernel parameters (the installer's, the image's `kargs.d` and the
       drivers' parameters stay). It can be withdrawn until the restart (the prepared version is deleted too)
     - at the next start, before login (`sloth-factory-reset.service`, with a label under the Plymouth animation):
       the apps go (system and user Flatpaks), `/etc` follows the factory `/usr/etc` (stays: accounts,
       machine name, language, keyboard, time zone, encryption, the machine's keys; on a domain-joined machine the login
       settings), the services follow the factory defaults, then it restarts
     - **Keep my files:** the files, the apps' data (e.g. Steam's games), the accounts, the Wi-Fi and the saved
       states stay; the desktop settings (`~/.config`) go into the "Old settings" folder, so Welcome
       starts again too
     - **Remove everything:** every account, home folder and saved state is deleted; Sloth Center asks for the new account's name
       and password before, and `sloth-first-user` creates it
     - Test: `tools/tests/test_factory_reset.py` (9 tests), resetting `/etc` on the real image's 4747 files, the
       whole startup step in both modes in a container (with accounts, together with first-user), the preparation
       with a fake rpm-ostree, the interface with an offscreen screenshot
   - [x] **Reset from the boot menu** (2026-10-20, the files stay): a GRUB menu entry in the system's language
     (in English for non-Latin scripts; `sloth_reset_title`, written by sloth-boot-ok), which sets a marker on the EFI partition
     (`sloth_reset=keep`) and restarts; `sloth-boot-reset.service` records it at the next start, and the existing
     `factory-reset boot` does it (without download and packages, with the version on the machine). "Remove everything" only from
     Sloth Center (it needs a new account). From now on `custom.cfg` is updated on existing machines too, if the template
     differs. GRUB syntax (`grub-script-check`) and the labels tried; tested on a real machine on 2026-10-21 (Esc, the entry,
     the reset runs)
   - [x] **Moving over from Windows** (2026-10-19): a new step in Welcome after sharing (only if there is an NTFS or
     BitLocker partition; it does not mount at startup, so it asks for no password), and from Sloth Center's Disks page too
     (`sloth-welcome --windows-import`). The Windows partition is only mounted read-only (udisksctl), and unmounted at the end (on
     closing too). Desktop, Documents, Downloads, Music, Pictures, Videos into the matching folders (xdg-user-dir), with a
     space check before; whatever is already there is skipped (it can continue), a clashing name gets a "(Windows)" suffix; `.lnk`,
     `desktop.ini` and junctions are skipped. Bookmarks (Chrome, Edge, Firefox) into one HTML file on the Desktop. The
     OneDrive folder is skipped (Cloud storage). A clear message for BitLocker and errors. `sloth_common/windows_import.py`,
     in 50 languages. Tried on a real NTFS partition (loop device) and in Welcome's interface (offscreen, with screenshots);
     still to test next to a real Windows

**Important, but not blocking the release:**
- [x] **More apps and Windows game launchers in Welcome** (2026-10-19, the user's request): 20 new Flathub apps
  (browser: Floorp, Tor Browser; office: Thunderbird, Obsidian, Joplin, Bitwarden; media: Elisa, Stremio, Plex,
  Jellyfin; chat: Zoom, Slack, Teams for Linux, Element, Viber; games: itch, RetroArch; creative: Audacity,
  darktable, Shotcut), and in the Games step the Windows launchers: Battle.net, EA app, Ubisoft Connect, Epic Games,
  GOG Galaxy, Rockstar Games (a new `windows` source in the catalog: downloading the official installer, a "Windows program ·
  you install it after the wizard" label, an explanation at the top of the step). If there is one, there is no Restart at the end: "Continue to
  installing the Windows programs" → Welcome hides, the installers open one by one in the .exe handler
  (`sloth-exe --queued`: the install starts at once, "Start" in a separate process, so the queue goes on), and at the end
  Welcome comes back with the Restart button. Icons are local (from the vendors' installers / Wikimedia Commons, NOTICE),
  in 50 languages. Tried: the download (EA app), the interface with screenshots, the queue with a fake sloth-exe; test the
  whole queue (Battle.net + EA app) on a real machine. Note: Ninite is not good for this (Windows only, it would install
  into one environment, and most game launchers are not in it)
- [x] **OneDrive and Google Drive as a folder** (2026-10-19): rclone (a Fedora RPM, for both), like Windows'
  "Files On-Demand": in the `~/OneDrive` / `~/Google Drive` folder every file is visible, only the opened ones are downloaded
  (full local cache, 30 days / 20 GB). Signing in in the browser (rclone's local callback), automatic answers to the setup's
  questions (`/usr/libexec/sloth-os/cloud-drive`); mounting: `sloth-cloud@.service`
  (a user service, by itself at login). Sloth Center → Account and security → Cloud storage (Sign in,
  Open, Disconnect), in 50 languages. kio-gdrive's Google sign-in got stuck on Google's blocks several times, so it is
  not that. Tried locally up to the sign-in; test with real accounts (OneDrive personal and business, Google)
- [x] **Connecting a phone** (the equivalent of Windows' "Phone Link"; 2026-10-19): KDE Connect is not on Flathub,
  so it came back as an RPM, but it is off by default (`slim-image.sh`: starting by itself, D-Bus activation and
  Start menu entries set aside), so it only runs and announces itself on the network for those who ask for it. Turning it on in
  Welcome (Chat, a new `system` source in the catalog) and in Sloth Center (Drivers and hardware, a switch);
  both call `/usr/libexec/sloth-os/phone-link on|off|status`, without a password. Tried locally.
  Test on a real machine: pairing with a phone; whether the firewall lets it through (Fedora's default zone leaves the ports
  1025–65535 open, check that it is so here too)
- [ ] **BIOS/firmware updates** (fwupd, LVFS; HP supports it too): Discover's fwupd plugin is part of
  `plasma-discover-libs`, and fwupd is in the image too (2026-10-19: in `tools.yml` to be sure), so in principle it
  already shows on Discover's Updates page. Check on the HP; if not, on Sloth Center's Updates page
- [ ] **Printer and scanner:** 2026-10-19: `hplip`, `sane-backends-drivers-scanners` and `skanpage` in `tools.yml`
  (the scanning app as an RPM, not a Flatpak: the HP scanners' driver would not be visible inside the Flatpak). Test with an HP
  printer and scanner
- [ ] **Child account and parental controls:** screen time, what may be installed, which apps may be started; on Sloth Center's
  Account and security page
- [ ] **Updating every app in one place, in Discover** (decision: 2026-10-16). Discover already updates every Flatpak
  that Welcome installs from Flathub (that is why it updated Steam right away too). Still to do:
  - [ ] **Our own Flatpak repository for the GitHub-package apps** (e.g. ArtCraft; this is the first step): a GitHub Action
    uploads them from the releases (with an SHA256 check) into our own signed Flatpak repository (e.g. Cloudflare R2 or
    SourceForge). Welcome installs from there, Discover updates from there, `sloth-github-bundle-update.timer`
    can go (switching the already installed ones to the repository once). Needs: storage and a GPG key in CI
  - [ ] **Windows programs in Discover:** our own Discover plugin (C++, a KDE module) that shows the installed
    Windows programs and the Proton update. Big work, and it must be maintained with every Plasma update; the
    programs (Battle.net, Steam, Epic…) update themselves anyway. First check whether a
    simpler way (e.g. AppStream data + Sloth Center's Updates page) is enough
  - [x] **System update in Discover** (2026-10-19): it turned out from the source that there is no double update.
    Universal Blue removes Discover's rpm-ostree plugin (`plasma-discover-rpm-ostree`) from the KDE image, so
    Discover only shows the apps; Sloth Center updates the system. Meanwhile `ublue-os-update-services`
    prepares the system update by itself (`AutomaticUpdatePolicy=stage`), and updates the apps (Flatpak) by itself 2 minutes
    after power-on and daily (on an unmetered connection). Done: an "Apps" part on the Updates page (what updates
    by itself, "Open in Discover"); the app updater does not run while Welcome runs (a drop-in for the
    `flatpak-system-update` / `flatpak-user-update` services)
- [x] Next to Windows: full protection of the boot order (2026-10-19; still to test with a real Windows): a Windows-side
  helper (`/usr/share/sloth-os/windows-helper/`: `Sloth-OS-boot.cmd` + `sloth-boot-order.ps1`, texts in 50 languages).
  It has to be started once in Windows (double-click, UAC): a scheduled task on every Windows start and daily,
  with system rights; if Windows Boot Manager went first, it puts Sloth OS back (`bcdedit /set {fwbootmgr}
  displayorder … /addfirst`), it leaves other orders (e.g. a USB stick) alone. From bcdedit's language-dependent output it only
  reads the GUIDs and the name "Sloth OS" (tried with fake Hungarian output). When installing next to Windows the installer
  puts it on the Windows Public Desktop (a "Sloth OS" folder), afterwards Sloth Center → Advanced settings
  → "Place the helper in Windows" (a clear message for a hibernated / fast-startup Windows)
- [ ] A separate NVIDIA ISO "for advanced users" (starts with the NVIDIA driver even without internet), if the hosting allows
- [x] A handler for Linux packages (.AppImage, .deb, .rpm; a clear message for Mac files) – phase 2 (2026-10-19,
  still to test on a real machine; details at phase 2)
- [x] .exe handler: "repair / reinstall" – phase 2 (2026-10-19: Sloth Center → Windows programs → Repair,
  Reinstall)
- [ ] **Application management, next steps** (on the 2026-10-19 base):
  - [x] Import from other places (2026-10-19, still to test with a real Lutris / Bottles): the Steam takeover
    generalized (`sloth_common/apps/imports.py`): Steam (`shortcuts.vdf`), Lutris (`pga.db` + `games/*.yml`, native
    and Flatpak), Bottles (`bottle.yml`, External_Programs), an earlier `~/.wine` (registry + shortcuts). "With the original
    app" (Steam / Lutris / Bottles starts it) or "Take over" (a reflink copy); the original is not touched
  - [x] Recipes from the shared knowledge (2026-10-19): `recipes.json` in the `sloth-os-knowledge` repository (edited by hand,
    the `recipes` Action checks it on every change and PR: `seed/validate_recipes.py`), and built into the image
    (`/usr/share/sloth-os/recipes.json`, without internet too); `sloth-windows-prepare` downloads it, the newer one (`updated`)
    wins. The machine checks it again too (`sloth_common/apps/recipes.py`): only allowed fields and values (launcher →
    client, the .exe files going into the Start menu and the ones to skip, components, Proton switches, arguments, turning DLLs off
    `=d`/`=b`; no command, arbitrary variable or native DLL). The data of the recipes written into the code moved over; only
    writing the settings files stayed in the code (Battle.net, Ubisoft). The first recipes: Battle.net, Epic, GOG Galaxy, Ubisoft Connect
  - [x] The Linux package handler (below) should install into `~/Applications` too (AppImage), with the same library
    (2026-10-19: `sloth_common/apps/packages.py` `install_appimage`, it updates in the background)
- [ ] Bringing Steam games into self-healing and the shared knowledge
- [ ] Sign-in, next steps (see phase 3, Account and security):
  - [ ] Storing the PIN in the TPM (now a scrypt hash under `/etc/sloth-os/pin`; the TPM would also limit the attempts
    in hardware, and the hash could not be taken to another machine)
  - [ ] Work account: Entra ID (next to the current Active Directory)
  - [ ] Opening the password store (KWallet) on a password-free login (PIN, fingerprint, security key): now
    it asks for the password at the first use
- [x] Developer panel in Sloth Center (repository, builds, testing from a GUI) – phase 3 (2026-10-19, see below)
- [ ] Extending the advanced settings continuously – phase 3. 2026-10-19: compressed memory reserve (zram: default /
  larger / off, `sloth-helper zram`, `/etc/systemd/zram-generator.conf`; checked with zram-generator in
  Fedora 44), PIN sign-in (Account and security)
- [x] ISO size: squashing the layers, a space-saving ISO build – phase 4 (2026-10-19, see phase 4)
- [x] (2026-10-20: it installs without errors now) Vivaldi did not install from Welcome (cause unknown; watch at the test). A possible cause: the
  automatic app updater above ran at the same time as Welcome (now it is skipped while Welcome runs)

## Earlier (2026-10-15)
- First test on a real machine (2026-10-15 afternoon, from a USB stick, a test laptop with Intel UHD). The bugs found are fixed,
  check again with the next image and ISO:
  - [x] In the live system the desktop stayed English after "Try": now Plasma restarts in the chosen
    language (`plasma-localerc` + the session's environment + restarting plasmashell)
  - [x] While installing, Welcome only showed the downloaded MB: now also which app (or which app's
    component) is downloading / installing, "x / y MB" while downloading; the progress bar follows the size
  - [x] Freshly installed apps (the Steam put on the taskbar too) had no icon until a restart: the Flatpak
    icon folder did not exist when Plasma started (no preinstalled apps). Now `tmpfiles.d` creates it
  - [x] Battle.net started after installing, then exited after about 10 s (through Steam it worked): the
    .exe handler now starts it according to Lutris' recipe (hardware acceleration off in Battle.net.config,
    `locationapi=d`), `sloth_exe/quirks.py`; the settings of the other launchers (EA, Ubisoft, Epic) can come here
  - Vivaldi did not install from Welcome (among the to-dos, see above)
- To do for 2026-10-15: a new ISO and a full VM test (account in the installer, first start without the KDE wizard, hidden
  GRUB and quiet boot, Welcome, desktop, Sloth Center, .exe handler); reviewing the gaming items; Developer panel.
- Every translation is done (Welcome, installer, .exe handler, Sloth Center: 50 languages); the native review is still to do.
- Fourth VM test (2026-10-15, Hyper-V): installing the morning ISO (6.9 GB) got stuck after `bootc`; the cause
  is found and fixed (phase 4). Also done the same day: the start menu names in all 50 languages, a slimmer image
  (the troubleshooting tools stay), Falkon instead of Firefox in the live system, a faster ISO build
  without podman commit, the screen does not turn off while installing.
- Next: CI rebuilds the image, then a new ISO (preferably on the stronger machine; the build needs about 45 GB of
  space), then a full VM test. In the VM dynamic memory should be off.

## Earlier (2026-10-14 evening)
- Third VM test (new ISO, 4 GB RAM, without internet): our own installer went through. Works: language switching,
  live keyboard switching in the test field, disk name (`vda · HDD · 43 GB`), focus frame, a moving progress bar,
  retrying after an error, the work partition (mounted system-wide over `/var/tmp`, afterwards the system partition
  grew to 39.5 GB), renaming the boot entry, writing the language/keyboard, copying Firefox without internet;
  KDE's welcome does not come up. The first start brings up Plasma Setup in Hungarian.
  We stopped there: Plasma Setup, creating an account (test / sloth). Next: Sloth Welcome (the new "Passwords"
  step), the desktop, Sloth Center's new pages, the .exe handler.
  New to-dos from the test:
  - [x] KDE's first-start wizard (Plasma Setup) is removed: the account is asked by the Sloth OS installer
    (a new "Your account" page), created on first boot by the `sloth-first-user` service; Welcome asks
    the rest. Still to test in a VM (needs a new image + a new ISO)
  - [x] The new ISO already needs the fixed installer helper (in the VM it was copied by hand): building a new ISO (2026-10-15)
- Second VM test (the first own ISO, 6.8 GB): hidden GRUB, boot without text, Firefox on the taskbar, switching the language
  in the chooser right away: fine. The install did not go through; the bugs found are fixed (phase 4, "Own installer"),
  but it must be checked again in a VM. Next step: a new ISO (`tools/build-iso.sh` on Linux, `tools/build-iso.ps1`
  on Windows; needs the GitHub CLI's `read:packages` scope), then a VM test to the end: install, first start, Welcome.
- Sloth Center's open phase 3 items are done (user services, environment variables,
  the list of versions, controllers, password-free administrator, sign-in methods, the Games module); still to test in a VM.
- Sloth Center's translation is done in all 50 languages (2026-10-15); the native review is still to do.
- Afterwards: installing next to Windows.

## Phase 0 – Base image ✅ (this repository)
- [x] Universal Blue Kinoite base, AMD/Intel + NVIDIA variants
- [x] Renaming (os-release)
- [x] Gaming packages: gamescope, mangohud, gamemode
- [x] Nothing preinstalled, not even Steam: the user chooses everything in the welcome wizard (the Firefox RPM goes too);
  only what they installed goes on the taskbar
- [x] The first successful build in GitHub Actions (both images)
- [x] Test in a VM and on our own machine. First VM test (2026-10-13), results:
  - [x] Hidden boot menu, Plymouth animation, the name "Sloth OS" (TTY, machine name, Plasma Setup "Under the hood: Sloth OS")
  - [x] Sloth Welcome starts full screen; switching the color theme works at once; the taskbar layout can be chosen; all 6 categories appear
  - [x] Installing apps from the wizard (2026-10-15, real machine: works; Vivaldi did not install)
  - [x] Fixed: the "Chat" category's icon was missing (`internet-chat` is not in Breeze; now `kopete`, fallback `dialog-messages`)
  - [x] Fixed: on the app cards the unselected ones showed a tick too (Breeze has no `checkbox-unchecked`, the ticked `checkbox` came instead); now a real checkbox and a stronger highlight
  - [x] Fixed: the color theme cards centred row by row, evenly distributed (7 cards: 4 + 3)
  - [x] Desktop, taskbar, Sloth Center, .exe handler, the splash screen during boot (checked in later tests)
  - [x] Fixed: Sloth Center did not open (`NameError` when loading the Updates module); check again in a VM
  - [x] Fixed: Windows apps with a launcher (e.g. Battle.net) closed after starting (always `waitforexitandrun`
    instead of `PROTON_VERB=run`); check again in a VM
  - Note: the text kickstart install sets `multi-user.target` (needed: `xconfig --startxonboot`),
    and if the installer does not create `/etc/plasma-setup-done`, KDE's Plasma Setup wizard comes up

## Phase 1 – Its own face
- [x] Logo: a matte silver sloth face, without an outline (`files/system/usr/share/sloth-os/logo/`, source: `docs/branding/`)
- [x] Distinct OS emblem: a silver-gray sloth hanging from a branch for the Start menu; the Sloth Center keeps its own icon. Fastfetch prints a matching Sloth OS ASCII logo.
- [x] Boot animation (Plymouth): a white dot running around the edge of the logo (`files/system/usr/share/plymouth/themes/sloth-os/`, preview: `docs/branding/boot-preview.gif`)
- [x] Hiding the boot menu (it only appears after a failed start) and a quiet boot: bootupd's GRUB template showed the menu for 1 s on every start, and it does not look at `menu_auto_hide`, so our own `custom.cfg` (`/usr/lib/sloth-os/grub-custom.cfg`, the state on the EFI partition, `sloth-boot-ok.service`); the `quiet rhgb splash` missing from the bootc install went into the kargs
- [x] Wallpapers: 16 pictures in 4K (with AI upscaling), the ultrawide ones in 5120×2160 too; default: "Metallic Sloth Over Silver Waves" (desktop and lock screen)
- [x] A Windows-like default Plasma layout: taskbar at the bottom, start menu with the logo, pinned apps; a splash screen with the boot animation after login (`files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/`)
- [x] Other layouts to choose in the welcome wizard: Windows 10, Windows 11 (centred), macOS-like (top bar + floating dock)
- [x] Color themes: Silver dark (default) and light, Snow White, Midnight Black, Mist Blue, Night Blue, Sage (`tools/branding/gen_colors.py`, preview: `docs/branding/color-schemes-preview.png`)
- [x] Our own Plasma theme: the style is done, nothing else is planned (decision: 2026-10-15)
- [x] Login screen (Plasma Login Manager, SDDM as a fallback): the Sloth OS wallpaper, Sloth Silver colors
- [ ] Check where the name "Fedora" or "Universal Blue" still shows. So far:
  - [x] System information, boot menu entries, machine name: they come from os-release (Sloth OS)
  - [x] KDE's welcome app (`plasma-welcome`) is removed from the image (`files/scripts/remove-default-apps.sh`), Sloth
    Welcome runs instead. The earlier turning off with `kded6rc` did not work (in the live system it covered the installer)
  - [x] Default wallpaper: our own Sloth OS wallpaper
  - [x] The firmware (BIOS/UEFI) boot entry's name: our own installer renames it to "Sloth OS" (because of an `lsblk` bug it
    did not run until now, fixed)
  - [ ] Look through in a VM: login screen, Discover, System Settings
  - [x] The Sloth tools' names and descriptions in the start menu in all 50 languages (2026-10-15; until then they showed in
    Hungarian in every language). The `.desktop` files are written by `tools/gen_desktop_entries.py` from the translations

## Phase 2 – Gaming that just works
- [x] Building in umu-launcher (the official GitHub RPM, a pinned version + SHA256: `files/scripts/umu-launcher.sh`)
- [x] Windows programs without Steam and without internet too: Proton is downloaded in advance in the background after login
  and kept fresh (`sloth-windows-prepare.timer`); if it is not there yet and there is no network, the system Wine starts it
  (`wine-core`, `wine-dxvk`, `wine-mono`; `sloth_exe/backend.py`)
- [x] **.exe handler** (`files/system/usr/lib/sloth-os/sloth-exe/`): double-click an .exe/.msi →
  install (a separate folder per program, the shortcuts into the Start menu) or start; the first time, downloading the
  components with progress. The user never sees the word "Wine", "Proton" or "prefix".
  - [x] The list of installed Windows programs and removing them in Sloth Center
  - [x] Editing the Start menu entries afterwards (Sloth Center → Windows programs → Start menu)
  - [x] Repair and reinstall in Sloth Center (2026-10-19)
  - [x] Per-game fixes automatically (umu database: GAMEID based on the program's name) – see below
- [ ] **A self-healing runner: every Windows program should start, without settings** (idea: 2026-10-15). There is no Proton
  setting good for everything (what one needs breaks another), so the system finds the working one per program
  by itself. The user only sees: "Starting…", and the program starts. Steps:
  1. [x] **Recognition** (`sloth_exe/identify.py`): from the .exe's version data (product name; "Launcher",
     "Setup", version number cut off) umu's database (it comes with the system, `sloth-windows-prepare` updates it),
     if it is not there, the Steam store (an exact name match) → `GAMEID=umu-<Steam AppID>`. That brings
     umu-protonfixes' fixes and Proton's own fixes tied to the AppID. It searches once, and remembers the result
  2. [x] **Recipes** for the known launchers (`sloth_exe/quirks.py`, based on Lutris' tried installers,
     adapted to Proton): Battle.net (GPU acceleration off, `locationapi=d`), Ubisoft Connect (overlay off,
     d3dcompiler_43), Epic (`-opengl -SkipBuildPatchPrereq`), GOG Galaxy (`libglesv2=d`, Visual C++, .NET 4.8,
     `/runWithoutUpdating /deelevated`). Lutris' recipes for the EA app and Rockstar only install fonts, and
     Proton brings those. Still to test with real launchers
  3. [x] **Diagnosis** (`sloth_exe/diagnose.py`): the runner's output always goes into the background
     (`<program>/naplo/<exe>.log`, without the "fixme" noise). If the program exits quickly, fixing the recognized errors:
     a missing DLL → the matching component (Visual C++ 2005–2022, DirectX parts, XAudio, PhysX, MSXML, VB6…,
     winetricks through umu); .NET → dotnet48; a Vulkan/DXVK error → WineD3D; a built-in browser
     GPU error → `--disable-gpu`
  4. [x] **Self-healing** (`sloth_exe/heal.py`): if there is no recognized cause, a sequence of attempts (default, without fsync,
     WineD3D, GE-Proton, an older Proton; at most 4 attempts per start, then a clear error message).
     Before a Proton switch a reflink snapshot of the program's folder (Btrfs; on other file systems the Proton switch
     is skipped, it can only step forward), restored after a failed attempt. It remembers the working setting per .exe.
     If a launcher hands over (e.g. Battle.net Launcher → Battle.net), that is not an error: it waits for it
  5. [x] **Rollback after updates:** after the working version it tries the newer one first; if that does not work, back to the
     working version (from the snapshot), and that program stays on it until an even newer one comes.
     `sloth-exe --maintenance` deletes the old Protons (the latest, one spare and the versions used by
     programs stay)
  6. [x] **Shared knowledge** (`sloth_exe/community.py`, service: `services/knowledge/`): what worked on other Sloth OS
     machines is the first attempt here. Reading: a static `knowledge.json` from the public
     `Sloth-OS-Linux/sloth-os-knowledge` repository (downloaded by `sloth-windows-prepare`). Sharing: only if the
     user turns it on (Sloth Center → Windows programs → "Share experiences", off by default);
     the report is anonymous (only a hash of the program's name, the machine is a random number), it is queued, and goes out
     in the background. The service is a Cloudflare Worker + D1 (`https://sloth-os-knowledge.slothos.workers.dev`):
     it only accepts allowed settings, one vote per machine, a setting is published if it worked on at least 3 machines and in
     75% of the cases, 500 reports a day per address. The summary is written hourly by the knowledge repository's
     GitHub Action (a monthly heartbeat, so the schedule does not stop)
     - [x] A separate step in Welcome (after Passwords): what it is, what goes out and what does not; the user chooses
       (yes / no, neither is selected in advance), it can be changed later in Sloth Center. Description: README
     - [x] A base from ProtonDB's open data (ODbL): every month the knowledge repository's `protondb` Action extracts from the latest
       release the working setting per game and GPU vendor (Proton variant, switches,
       components; only the last 2 years, at least 3 reports, only if not the default). 2026-10: 287
       games. For recognized games (with a Steam AppID) this is the first attempt if there is no own or Sloth OS data
     - [x] More allowed switches: NVAPI, hiding NVIDIA, large address aware, heap delay free,
       D3D10/11 off, old GL strings, write watch off (in the Worker, on the machine and in the ProtonDB processor too)
     - [x] Monitoring the service (2026-10-16): the knowledge repository's `monitor` Action checks the Worker daily, the
       validation of reports and the export; on an error an issue opens (e-mail), it is closed when things are fine again.
       The error path has not been tried live yet
  - Tried (2026-10-15) with the real controller and a fake runner: a missing DLL, a Vulkan error, an unknown
    crash, rollback after an update on Btrfs, a hopeless case, a launcher handover, leftover Wine processes.
    Partly tried on a real machine since (Battle.net, EA app, Ubisoft Connect)
  - Test: going through the big launchers (Battle.net, EA, Ubisoft, Epic, Rockstar, GOG) and a few popular games
    after every bigger change, on a real machine (AMD, NVIDIA, Intel)
- [x] Proton on by default in Steam for every game (`sloth-steam-proton-default.service`)
- [x] MangoHud / gamescope Flatpak Vulkan layers for the Steam Flatpak (`sloth-steam-vulkan-layers.timer`)
- [x] A clear error message if a game cannot run on Linux because of anti-cheat (.exe handler: it says so right away for Vanguard, FACEIT, Ricochet…; for Easy Anti-Cheat / BattlEye if the game exits quickly). Still to do: the same for Steam games
- [x] **A handler for Linux packages** (2026-10-19, still to test on a real machine): the .exe handler opens them (it recognizes them
  by the file's contents), shared code: `sloth_common/apps/packages.py`. AppImage: under `~/Applications/<name>/`
  (a copy, with a reflink on Btrfs), made executable, into the Start menu with its own name, icon and categories
  (`sloth-exe --run`, it starts after moving too), or only running it; FUSE 2 (`fuse-libs`) is in the image.
  .deb: into an Ubuntu box (`sloth-ubuntu`), .rpm: into a Fedora box (`sloth-fedora`), the new apps into the Start menu
  (`distrobox-export`), next to it "Search in Discover"; on removal it is deleted from the box too. Mac files: a clear
  message and a Discover search; we do not run Mac command files. That is why Sloth Center's page became "Programs".
  The data of programs without files of their own (started from elsewhere, boxed) is hidden
  (`~/.local/share/sloth-os/apps/`), so there is no empty folder in `~/Applications`. Also done (2026-10-19):
  AppImage updates in the background (`sloth-exe --maintenance`, called by `sloth-windows-prepare.timer`): from the AppImage's own
  update data (ELF `.upd_info`: `zsync|…` or `gh-releases-zsync|…`) the `.zsync` header; with an SHA-1 match
  nothing to do, otherwise a full download, check, replace; only on an unmetered connection, and if the program is not
  running. Tried on a real AppImage (AppImageUpdate): reading the data and the header. If a .deb, .rpm or
  AppImage is on Flathub too (an exact name match), we recommend that ("Install from Discover" is the main button).
  The original plan: Linux apps downloaded from the net should install
  on a double-click too, with progress, a Start menu entry, and be removable in Sloth
  Center. Until then nothing handled any of them:
  - `.AppImage`: not executable when downloaded, a double-click brings "Open with…"; many need `libfuse2` too
    (check whether it is in the image). Plan: into its own folder, executable, Start menu, updating if the
    AppImage supports it
  - `.deb`: cannot be installed on Fedora at all. Plan: in the background into an Ubuntu box (`distrobox`, Sloth
    Center's box management already exists), the app appears in the Start menu like a native one, the word "box" is not shown
  - `.rpm`: cannot be installed "just like that" on an Atomic system. Plan: if it has a Flatpak version, we recommend that;
    otherwise into a Fedora box; layering into the system only in the advanced settings
  - `.flatpakref` / `.flatpak`: Discover already handles them (check in a VM)
  - Mac apps and disk images: `.dmg`, `.xip`, `.pkg`, `.mpkg`, `.app` (in a zip too: `.app.zip`), `.sparseimage`,
    `.sparsebundle`, `.cdr`, `.smi`, old `.img` / `.dc42` disk images, and iOS apps (`.ipa`).
    Recognition by MIME type too (e.g. `application/x-apple-diskimage`, `application/x-xar`); the `.command` /
    `.tool` scripts are shell scripts, for these only a warning. They cannot run on Linux (Darling is experimental,
    it does not run graphical apps), so
    a clear message: "This program was made for Mac, it does not run on this computer"; if the app is on Flathub (e.g.
    Spotify, Discord, VS Code), we offer its Linux version with one click; the files in it
    (font, document) can be extracted with Ark

## Phase 3 – Our own GUI tools
Goal: **every terminal task should have a graphical equivalent.** Where KDE already has a good GUI, we use that
(and check that it is preinstalled); where there is none, our own tools fill the gap (Python + PySide6/QML,
operations needing permission through polkit, with a password window).

### Our own tools
- [x] **Welcome wizard** at the first login (`files/system/usr/lib/sloth-os/sloth-welcome/`):
  color theme, then in separate steps per category browser, office programs, music and video, chat, games,
  creative (with ArtCraft in it). Nothing is selected by default; installing with progress, retrying on a network
  error; the browser goes on the taskbar.
  - [x] Choosing the taskbar layout
  - [x] Multilingual: in all 50 usable languages of the Fedora installer (where Anaconda is at least half
    translated, plus Norwegian Bokmål), with right-to-left writing (Arabic, Hebrew) and fonts for every script
    (`sloth_welcome/translations/*.json`, check: `tools/check_translations.py`); by default it starts in the system's language,
    it can be switched on the first page. Sloth Center is translated into all 50 languages too.
    Still to do: native review (the translations were made by AI)
  - [x] Quick buttons at the end: Steam sign-in, online accounts, language and region (the installer asks for the language)
  - [x] Updating ArtCraft: a user install + a daily background updater (`sloth-github-bundle-update.timer`, with an SHA256 check)
- [ ] **Sloth Center** (one app, split into modules; `files/system/usr/lib/sloth-os/sloth-center/`):
  - [x] Updates and rollback (check, install with progress, restart, back to the previous one, keeping the current version);
    the list of every version on the machine: any of them can start next time without downloading (`ostree admin set-default`),
    and can be kept one by one
  - [x] Drivers and hardware: recognizing the graphics card, switching between the NVIDIA ↔ AMD/Intel versions (`rpm-ostree rebase`),
    enrolling the Secure Boot key with a step-by-step guide (`mokutil`); still to test on a Secure Boot machine with NVIDIA.
    Controllers: the list of connected ones (cable / Bluetooth, battery level), pairing and trying the buttons
    with KDE's modules. Note: while the repository was private, switching needed a registry sign-in (Developer panel →
    Sign in to the package registry, 2026-10-19)
  - [x] A shared administrator helper (`/usr/libexec/sloth-os/sloth-helper` + polkit `org.slothos.helper`): fixed operations, with a graphical password prompt
  - [x] Administrator without a password prompt (Sloth Center → Account and security, and simplified in Welcome's "Passwords"
    step): a polkit rule per topic (`/etc/polkit-1/rules.d/49-sloth-admin.rules`, source:
    `/etc/sloth-os/admin-policy.json`, written by `sloth-helper admin-policy`, always only for the calling user),
    sudo without a password (`/etc/sudoers.d`), automatic login (Plasma Login Manager). Still to test in a VM
    (`pkcheck`). Still to do: opening the password store (KWallet) automatically on an automatic login; administrator
    rights can be set in KDE's Users module. The original plan:
  - Administrator without a password prompt: when creating the account (installer / first start) one can choose whether the user
    is an administrator, and if so, whether to ask for a password for administrator operations. If not, everything
    runs without questions (a polkit rule for the user or a separate group, e.g. `/etc/polkit-1/rules.d/`, + sudo NOPASSWD).
    Not just "for everything / for nothing": it should be choosable per topic what needs a password (installing programs,
    updating, network and devices, date and language, services and drivers, disks, users and passwords,
    booting and system packages; the last three protected by default), plus automatic login,
    opening the password store (KWallet) automatically, the password in the terminal (sudo). It should also be changeable
    later in Sloth Center, without a terminal
  - [x] Sign-in methods based on the hardware (Sloth Center → Account and security; only what the hardware supports
    is shown): fingerprint (`fprintd`, enrolling in KDE's Users module, turning on with `authselect`
    with-fingerprint), security key (FIDO2/YubiKey: enrolling with `pamu2fcfg`, `authselect` with-pam-u2f), work
    account (Active Directory: `realm join/leave` from a form). Fingerprint tested on a real machine (2026-10-21).
    Still to do: Entra ID, opening the password store on a password-free login. The original plan:
  - [x] PIN (2026-10-19; the PAM part tried with `pamtester` in a Fedora 44 container:
    `tools/tests/pin_pam_test.sh`, 14/14; works on a real machine on the login and lock screens, 2026-10-21): Sloth Center →
    Account and security, 4–8 digits, easy-to-guess ones (1111, 1234…) forbidden. Our own authselect profile
    (`vendor/sloth` = Fedora's `local` + with-sloth-pin, `files/scripts/pin-authselect.sh`); a
    `pam_exec` line goes before pam_unix (`/usr/libexec/sloth-os/pin-check`), so both the password and the PIN can be typed into the same field.
    The PIN as an scrypt hash in `/etc/sloth-os/pin/<user>.json` (`sloth-helper pin-set/pin-remove`); only
    accepted in local services (login, lock screen, approval), never remotely (ssh);
    after 5 wrong attempts a longer and longer wait (at most 1 hour), the password works meanwhile. Storing in the TPM: later
  - [x] Face recognition: decision (2026-10-19), not built in for now. Howdy is only available from personal COPRs,
    and it would go into PAM (a bug in it affects logging in); if there is an infrared camera, the Account and security page
    explains this and recommends the PIN or the fingerprint. Look again if a maintained solution gets into Fedora
  - Sign-in methods based on the hardware (wizard + Sloth Center; the machine recognizes what it can do and offers only that):
    password; a PIN with 4/6/8 digits (our own PAM module, only a hash stored on the machine, preferably with the TPM, waiting after
    failed attempts); fingerprint (`fprintd`, if there is a supported reader); face recognition (Howdy, only with an
    infrared camera, like Windows Hello; not in the Fedora repositories); a work account (Active Directory: `realmd` + `sssd`,
    joining a domain from a GUI; later Entra ID); a security key (FIDO2/YubiKey, `pam_u2f`).
    There is no finished solution yet for a phone passkey for local login on Linux, keep watching.
    Note: with a PIN, fingerprint or face the password store (KWallet) does not open by itself, this has to be solved
  - [x] System packages (advanced): RPM layering and removal (`rpm-ostree install/uninstall`)
  - [x] Booting (advanced): kernel parameters (`rpm-ostree kargs`), showing the boot menu for dual boot
  - [x] Services: the common ones with understandable names and switches, an advanced list with start/stop (`systemctl`);
    the user's own services without a password (`systemctl --user`), the session's basics are protected
  - [x] System health: a "What is wrong?" view in plain language (storage, services that did not start, crashes, out-of-memory, graphics card and disk errors, temperature), saving the log for asking for help (`journalctl`)
  - [x] Disks: the drives' usage, health (SMART) and temperature, deleting unneeded app components (`df`, `smartctl`, `flatpak uninstall --unused`)
  - [x] Developer environments: creating and deleting boxes (Ubuntu, Debian, Arch, Fedora), installing programs into the box, apps into the Start menu (`distrobox`); still to test in a VM
  - [x] Environment variables and startup settings (Advanced settings): your own variables in
    `~/.config/environment.d` without a password, the other programs' variables shown, the risky ones
    (e.g. `PATH`) marked; programs started at login: KDE's Autostart module
  - [ ] Advanced settings: every system setting that has no KDE GUI (grows continuously)
- [x] **Games:** per-game settings (FPS display: MangoHud, upscaling: gamescope FSR, performance mode:
  GameMode) without the words Proton/Wine (Sloth Center → Games). For Steam games it goes into the launch options
  (`localconfig.vdf`, the user's own entries stay; it can only be written while Steam is closed, the interface closes it),
  for Windows programs into the program's data (`.sloth/app.json`), and the .exe handler applies it when starting
  (`sloth_common/gamesettings.py`). The upscaling drop-down tested on a real machine (2026-10-21); still to test with real games

### Existing KDE / Flatpak GUIs (check that they are in the image)
Decision (2026-10-15): only what is essential for the system to work stays in the image; the rest
can be installed from Discover. What stays: Partition Manager, System Monitor, Dolphin, Konsole, Discover,
System Settings, KWrite, Ark, Spectacle, firewall settings, printers, Bluetooth, the Orca screen reader,
the password store (KWallet), the Chinese/Japanese/Korean input methods, `podman` + `skopeo`, and whatever our own tools
use. **The tools needed for troubleshooting stay too** (daily use needs no terminal, but if
something breaks, there should be something to fix it with): log viewer (kjournald), Filelight (what takes the disk), `nano`, `vim`,
`htop`, `nvtop`, `tmux` (on a text console too), remote help (KRdp / krfb).
- [x] Removing the rest (`files/scripts/slim-image.sh`, at the end of the modules): Kate (KWrite stays), KDE Connect,
  Help Center, `just` (with `ublue-os-just`), `toolbox` (`distrobox` stays), `buildah`, `cosign`, `ibus`
  (fcitx5 stays, Chinese/Japanese/Korean input works with it too), the KDE and Fedora wallpapers, BlueBuild's
  nushell plugins. Checked package by package what depends on them; tried locally: `/usr` 9612 → 8751 MB.
  `git` stays (to decide). Still to check in a VM that everything needed is there
- [ ] Apps and updates: Discover · Flatpak permissions: System Settings
- [ ] Firewall (`firewall-cmd`): System Settings' firewall module
- [ ] Partitions (`fdisk`, `mkfs`): KDE Partition Manager
- [ ] Processes (`top`, `kill`): System Monitor
- [ ] Network, VPN, printers, users, machine name: System Settings

### Developer panel (for developing Sloth OS) – done 2026-10-19 (still to test on a real machine)
Sloth Center → Developer panel (`sloth_center/devpanel.py`), without terminal, `gh` and `cosign` (it calls the GitHub REST API
directly; the GitHub calls tried live):
- [x] Connection: repository and GitHub token; a button creates the token on GitHub with the scopes filled in (repo,
  workflow, read:packages); it goes into the password store (`secret-tool`; if there is none, a file only the user can read)
- [x] Builds: the state of the latest runs, starting image and ISO builds, opening on GitHub, Actions minutes this month
  (if the token and the account allow it)
- [x] Signing key: whether `SIGNING_SECRET` is set; a new key pair with cosign in Podman; the panel commits `cosign.pub`,
  puts the private key on the clipboard, and opens the GitHub secrets page (uploading the secret directly would need
  libsodium). When changing the key it warns: installed machines' updates stop until the new key reaches them with an update
  still signed with the old one
- [x] Trying out: signing in to the package registry (`sloth-helper registry-login`, `/etc/ostree/auth.json`), switching to a
  build (the `<commit>-<Fedora version>` tag, rpm-ostree rebase) and back to the latest, a virtual machine (GNOME Boxes)

## Phase 4 – Release
- [x] Making the repository public, turning the daily automatic build back on (`.github/workflows/build.yml`) (2026-10-21)
- [x] **Our own Sloth OS installer** (`iso/`): a live system from the USB stick, trying without installing, without Anaconda
  - [x] First version: language (Welcome's 50 languages), keyboard, time zone, installing on the whole disk
    (our own partitioning + `bootc install to-filesystem`, the image is in the ISO, it works without internet too),
    progress bar, restart; the installer asks for the account too (it is created on first boot). Build:
    `tools/build-iso.sh` (Linux) or `tools/build-iso.ps1` (Windows), locally with Podman, or `.github/workflows/iso.yml`
  - [x] The installer in all 50 languages
  - [x] A full-screen "Try / Install" chooser; a browser in the live system for trying
    (Falkon since 2026-10-15; no browser goes into the installed system, the user chooses in Welcome)
  - [x] Hidden GRUB on the ISO (Esc brings it up); the firmware boot entry's name is "Sloth OS" (not "Fedora")
  - [x] A smaller ISO: the image to install unpacked, the shared files only once (goal about 5 GB)
  - [x] The bugs of the second VM test (2026-10-14) fixed:
    - with 4 GB of RAM the install ran out of memory (`bootc` unpacked the layers into `/var/tmp` in RAM):
      now it uses a temporary work partition at the end of the disk, which it then adds to the system partition;
    - at the end of the install it did not find the root partition, and did not rename the boot entry either (`lsblk --json`
      gives a flat list without `--tree`); the progress bar stood at 36% during the copy (now it follows the data written to disk);
    - KDE's welcome covered the installer; the chosen keyboard did not switch in the live system
      (so the test field showed nothing; now `kwriteconfig6 --notify`, and KWin does not follow locale1);
    - with the keyboard: the arrows did not work in the opened lists, the focus was not visible; the disk's name was
      "0x1af4" (now vendor, model, HDD/SSD/NVMe)
  - [x] ISO build without podman commit (2026-10-15): the unpacked storage of the image to install goes into a separate folder
    (`iso/payload.sh`), and it is mounted into the live system when the ISO is made. The commit that alone took an hour and a half
    on the slow machine is skipped. On the old way `mksquashfs` skipped about 1000 whiteouts ("Cannot stat … ignoring");
    this probably did not break the install (the storage puts the layers together from the `tar-split` headers),
    and on the new way the whiteouts stay as `.wh.` files (tried, the layers' checksums match
    after squashfs and overlay too)
  - [x] Fourth VM test (2026-10-15, Hyper-V, generation 2 VM): `bootc` went through ("Installation complete!"),
    then the helper stopped without a log ("Installation failed"). Cause: at the end `bootc` remounts the target
    read-only, and setting up the boot menu (`custom.cfg`) threw an exception. Fixed: before writing it remounts it
    writable, and the helper writes every unexpected error into the log
  - [x] While installing, the screen does not turn off, lock, or the machine go to sleep (the live system's settings in
    `livesys-session-extra` + the installer's D-Bus inhibition for the duration of the install)
  - [x] `tools/build-iso.ps1`: runs `build-iso.sh` directly in the Podman machine's WSL distribution (until now
    it downloaded the image twice, and the Windows → ssh → Podman path got stuck under heavy load); WSL needs
    cgroupfs and containers without cgroups (`build-iso.sh` sets it by itself)
  - [x] A space-saving ISO build (2026-10-19): the temporary OCI copy
    (about 12 GB) is skipped, the unpacker reads directly from the downloaded storage (mounted in, as a
    `containers-storage:[overlay@…]` source; tried with a small image in Podman on WSL). The peak is about 25–28 GB this way.
    CI does not download the image twice either. Hardlinking the unpacked copy to the downloaded layers was left out
    (containers/storage's own files, too risky)
  - [x] ISO size (2026-10-15: 6.9 GB, of which the squashfs 6.2 GB; zstd-19 stays; the 1.0 ISO: 6.2 GB):
    - [x] Only Sloth OS's own wallpapers stay, BlueBuild's nushell plugins are removed
      (`files/scripts/slim-image.sh`; the installed system is smaller too)
    - [x] Falkon instead of Firefox in the live system (decision: 2026-10-15): KDE, based on QtWebEngine/Chromium; an RPM,
      QtWebEngine is already in the image, so about 14 MB instead of the Firefox Flatpak's about 0.5 GB.
      Only in the live system (`iso/build.sh`); when installing without internet no browser is copied,
      the user chooses in Welcome (9 browsers now)
    - [x] Squashing the layers of the image to install into one, with a switch (2026-10-19): `SLOTH_SQUASH=1`
      (`tools/build-iso.sh`), `-Squash` (`tools/build-iso.ps1`), `squash` (CI). The replaced / deleted files (e.g. the
      old kernel) drop out; estimate: 0.5–1 GB. The price: the first update downloads the whole image, so it is off by default;
      for releases. Used for the 1.0 ISO
  - [x] Installing next to Windows (2026-10-15; still to test with a real Windows): on the disk chooser, for a disk with Windows,
    "Next to Windows" (default) or "erase the whole disk", with a size slider. The helper surveys the disk
    (`sloth-install-helper probe`): UEFI and GPT are needed; the existing free space if it is enough, otherwise shrinking the largest
    NTFS partition (C:) with `ntfsresize` (Windows keeps 20 GB of free space). Sloth OS gets its own EFI
    partition (Windows' one is not touched), the boot menu is shown, with Windows in it (`EFI/fedora/sloth-windows.cfg`,
    to a Windows boot loader on any disk), the hardware clock keeps local time. It recognizes and clearly
    explains: BitLocker (space has to be freed in Windows; it warns about the recovery key),
    fast startup / hibernation (from the header of `hiberfil.sys`), a pending disk check, BIOS mode, an MBR disk,
    too little space. Tried on a loop device: shrinking (the files intact, the partition's start unchanged), free
    space, hibernated Windows, BitLocker with and without free space. In a VM and in the container test (2026-10-21) the whole install
    and the Windows entry of the boot menu work
    - [x] Protecting the boot order (`sloth-boot-order.service`): if a Windows update put "Windows Boot Manager" at the
      front of the order, Sloth OS goes back to first place at its next start (it leaves other things, e.g. a USB stick put
      first, alone). Limit: until then the machine starts Windows; Sloth OS has to be chosen once from the machine's own
      boot menu. The Windows-side helper (2026-10-19, see the to-dos above) prevents this
  - [x] On an NVIDIA machine the NVIDIA version automatically (2026-10-15; still to test on a real NVIDIA machine): only the
    AMD/Intel one fits on the installer ISO, so the installed system handles it: `sloth-nvidia-auto.timer`
    (2 minutes after startup, then hourly until it succeeds) with an NVIDIA card, `rpm-ostree rebase` in the background
    to the NVIDIA image, with Secure Boot it also prepares enrolling the key; it runs once (it does not overwrite switching back
    by hand). A notification for the user (`sloth-nvidia-notify`): "Restart now" or the guide on Sloth Center's
    Drivers page (`sloth-center --page drivers`)
  - [x] Updates with signature verification after installing (`ostree-image-signed`; 2026-10-16): both images
    accept the other variant's signature too (`files/scripts/signing-family.sh` after the signing
    module; otherwise switching AMD/Intel <-> NVIDIA would get stuck). The installer writes the signed reference if
    policy.json requires a signature (otherwise the old one stays, so there are updates). Older installs are
    switched once by `sloth-signed-updates.timer` (the prepared version waiting for a restart too)
  - [x] Disk encryption (2026-10-16; tested on a real machine 2026-10-21, with the password prompt at boot): on the
    disk chooser "Encrypt the disk" (by default with the account's password, or a separate one; at least 8 characters),
    on a whole disk and next to Windows too. LUKS2 on the system partition (TRIM enabled), a separate unencrypted
    /boot (1 GB; GRUB cannot open LUKS2), `rd.luks.uuid` and crypttab. The password prompt runs with the chosen
    keyboard layout (`rd.vconsole.keymap`; every layout in the initramfs:
    `/usr/lib/dracut/dracut.conf.d/90-sloth-luks.conf`), the Plymouth theme shows a padlock icon instead of text
    (systemd's text is English and technical). Tried on a loop device: right/wrong password, LUKS2, TRIM, /boot, crypttab,
    the file system fills the partition. Fixed meanwhile: next to Windows it took all of the free space instead of the
    chosen size
  - [ ] Old (BIOS-only) machines (after 1.0)
  - [x] Downloading the ISO: on SourceForge (2026-10-21; GitHub releases allow at most 2 GB per file)
- [x] Website, download, documentation (sloth-os-linux.github.io, 2026-10-21)
