# Sloth OS installer ISO

This folder builds the bootable Sloth OS USB image: a live system you can try without installing,
with the Sloth OS installer starting automatically.

## How it works

- `Containerfile` + `build.sh` turn the published Sloth OS image into a **live system image**:
  a live-boot initramfs (`dracut-live`), automatic login (`livesys-scripts`), the installer, and a copy
  of the Sloth OS image itself in unpacked container storage, so installing works offline (files shared
  with the live system are stored only once in the ISO).
- [Titanoboa](https://github.com/ublue-os/titanoboa) turns that image into an ISO (`iso.yaml` sets the boot menu).
- The **Sloth OS installer** (`files/usr/lib/sloth-os/sloth-installer/`, Python + QML) asks for language,
  keyboard, time zone, the user account and the disk, partitions the disk itself and runs
  `bootc install to-filesystem` through a small
  root helper (`files/usr/libexec/sloth-os/sloth-install-helper`, via polkit). It writes the chosen
  language, keyboard and time zone into the installed system's `/etc`, plus the account details (the password
  only as a SHA-512 hash, root-only). On first boot `sloth-first-user.service` creates the account (as an
  administrator) before the login screen. KDE's own first-start wizard (Plasma Setup) is not in Sloth OS.
- Nothing in this folder ends up in the installed system.

The first version installs to a **whole disk** only (UEFI). Installing next to Windows is planned
(see `docs/ROADMAP.md`).

## Building

- Locally on Linux (rootful Podman via sudo): `tools/build-iso.sh` → `out/sloth-os.iso`
  (`SLOTH_BUILD_DIR` sets where the ~40 GB of build data goes)
- Locally on Windows (Podman, rootful machine): `tools/build-iso.ps1` → `out/sloth-os.iso`
- On GitHub: Actions → `iso` → Run workflow. While the repository is private the ISO is too large to
  upload, so the workflow only checks that it builds.

Both need read access to the (currently private) image on ghcr.io.

## Testing the installer UI without erasing a disk

Start the installer with `SLOTH_INSTALL_DRY_RUN=1`: it walks through all steps with simulated progress
and never touches a disk.
