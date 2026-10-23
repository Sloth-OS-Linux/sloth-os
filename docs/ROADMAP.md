Warning: truncated output (original token count: 32678)
Total output lines: 1301

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

### Sloth OS 1.0.3 (in preparation)
- [ ] **Critical** — Resolve the Fedora 44 `rpm-ostree` crash during OCI image updates (`2026.3-2.fc44` aborts
  with `JoinHandle polled after completion` while importing layers), then verify a full update stages and boots.
- [ ] **Medium** — Show OCI layer progress in Sloth Center, stop the spinner and explain the failure if the
  transaction connection closes, and reconnect to `rpm-ostreed` after a daemon restart. Verify the flow without
  requiring a terminal.

#### Windows program launch follow-up (2026-10-22)
- [x] **Reddit Desktop in a Fedora box:** package installs now fail visibly if a new desktop entry uses `sloth-exe`,
  if export fails, or if the exported host `.desktop` lacks a `distrobox-enter` command or still invokes `sloth-exe`.
  The running Fedora box no longer has the Reddit package's source desktop entry, so a live relaunch could not be
  reproduced; `tools/tests/test_apps.py` checks that invalid exports cannot be recorded as successful installs.
- [ ] **Medium** — Notepad++ starts again after closing: the install succeeded, but the start handler exited after 4–9 seconds
  and cycled through four runner settings even though the user saw the app open. Improve detection of a live Windows
  process after `umu-run` exits (check the prefix's Wine processes/wineserver), and only start another recovery attempt
  after confirming the previous app is no longer running. Reproduce that closing the app does not reopen it.
- [ ] **Medium** — 7-Zip required repeated installs: the saved log has one installer run, four quick-exit recovery attempts,
  and then a `7Z2605` Start menu entry. Reproduce the install and launch flow, then fix recognition or process tracking
  so a successful install is not mistaken for a failed app launch and repeated installation is unnecessary.

#### Installation and storage
- [ ] **Large** — Ask what to do with additional disks and partitions during installation. Leave them untouched and
  unmounted by default; only format after explicit selection and confirmation, then offer automatic mounting.
  In the “Next to Windows” flow, protect Windows, EFI, recovery, MSR, and BitLocker partitions. Test both
  installation flows on multi-drive systems.
- [ ] **Medium** — Before disk changes, run a compatibility check for boot mode, free space, Secure Boot, and Windows
  encryption or hibernation. Explain blockers and safe next steps in plain language.
- [x] Show the target disk and planned erase/resize/create/format/mount operations on the installer's confirmation page;
  the existing confirmation checkbox is required before applying changes. The temporary install partition is identified
  as mounted only during setup and deleted at the end.
- [x] Guide users through creating Sloth OS installation media, with a clear warning before erasing a USB drive.
- [ ] **Large** — Help users selectively migrate personal documents and supported browser data from Windows, with a preview.
- [ ] **Medium** — Show storage health warnings when supported, and help users back up important files if a drive may be failing.
- [ ] **Medium** — Identify reclaimable storage, estimate the space to be freed, and let users review items before cleanup.

#### Sloth Center, setup, and support
- [x] Add a system status page with OS version, update status, available storage, and a direct Feedback link.
- [x] Offer a short first-run guide to Updates, Programs, Games, backups, Feedback, and Disks; users can skip it or
  reopen it from the sidebar.
- [ ] **Medium** — Add a system and driver overview for graphics, audio, Bluetooth, and connected peripherals, with guidance
  when something needs attention.
- [ ] **Medium** — Add an application privacy overview for microphone, camera, and location access where supported.
- [ ] **Medium** — Add a security overview for disk encryption, Secure Boot, and updates, with plain-language guidance.
- [ ] **Large** — Offer a privacy-reviewed diagnostic bundle for Feedback. Redact personal data, let users review it, and
  require their choice before attaching it.
- [ ] **Medium** — Add guided Wi-Fi troubleshooting that checks adapter detection, Wi-Fi state, and connectivity, then
  offers understandable next steps.
- [ ] **Medium** — Keep essential installation, recovery, and troubleshooting help available offline.
- [ ] **Large** — Make temporary, limited guest accounts easy to create without exposing the owner's personal files.
- [ ] **Large** — Provide accessible controls for text scaling, contrast, screen reader, and keyboard navigation.
- [ ] **Medium** — Manage startup applications: explain what launches at sign-in where known, and show startup impact.
- [ ] **Large** — Gather laptop power-saving and performance modes, display and sleep settings, and supported battery
  health or charge limits in one place, with clear effects on battery life and gaming.

#### Updates, backup, and recovery
- [x] **Quick** — Explain that updates download the needed system parts, their size varies, free disk space is needed, and a restart applies the new version.
- [ ] **Medium** — Let users schedule updates and avoid restart prompts during user-defined quiet hours.
- [ ] **Medium** — Let users limit update download speed and warn before large downloads on metered or mobile connections.
- [x] Show backup availability and last backup time in Sloth Center (File backup page).
- [ ] **Medium** — Let users schedule file backups, choose retention, and estimate required storage.
- [ ] **Medium** — Verify backups by checking readability and guiding users through restoring a selected file.
- [ ] **Medium** — Back up and restore Sloth OS settings after reinstalling or when moving to another machine.
- [ ] **Large** — Protect game saves, including saves without built-in cloud support; show backup status and help restore them.
- [ ] **Medium** — Offer system rollback after an update from Sloth Center, with a clear explanation and restart flow.
- [ ] **Large** — Before significant settings or driver changes, offer a recoverable state and a clear way to revert.

#### Gaming, devices, and connectivity
- [ ] **Large** — Add an optional gaming mode that applies performance and notification settings while a game runs, then
  restores normal settings when it closes.
- [ ] **Medium** — Add a performance display for frame rate, system load, and supported temperature sensors.
- [ ] **Medium** — Make it easy to test and select controllers, microphones, and audio output devices before gaming.
- [ ] **Medium** — Share concise, community-informed game fixes with version details and a way to report outdated guidance.
- [ ] **Large** — When a game fails or crashes, offer a readable diagnostic summary and relevant, verifiable fixes.
- [ ] **Medium** — Help users move supported game libraries between drives without downloading again, updating launcher paths.
- [x] **Quick** — Show network status and latency, with basic guidance when the connection may affect online play (2026-10-23, Sloth Center's System status page).
- [ ] **Medium** — Help configure NAS devices and shared folders, preserving the connection after restart when requested.
- [ ] **Large** — Allow consent-based file sharing with another device on the local network without a cloud service.
- [ ] **Medium** — Help configure monitor resolution and refresh rate, plus HDR or VRR where supported.
- [ ] **Medium** — Let users save and quickly switch display and audio profiles, such as desktop, TV, or headset setups.
- [ ] **Medium** — Maintain hardware and game compatibility notes, including which GPU, controller, and settings worked well.

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
  on a real machine: a resta…17678 tokens truncated…loth Center
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
