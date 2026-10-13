# Sloth OS 🦥

A Linux desktop for everyday use and gaming that an average user can use just like Windows: **no terminal required**.

- **Base:** Universal Blue `kinoite-main` / `kinoite-nvidia` (Fedora Atomic + KDE Plasma)
- **Updates:** atomic, in the background; if something breaks, roll back to the previous version from the boot menu
- **Apps:** Flatpak (Flathub)
- **Build:** [BlueBuild](https://blue-build.org) + GitHub Actions; a new image is built after every commit and daily

## Layout

```
recipes/
  recipe.yml          # AMD / Intel image
  recipe-nvidia.yml   # NVIDIA image
  branding.yml        # name, logos, default settings
  gaming.yml          # gamescope, mangohud, gamemode...
  apps.yml            # preinstalled Flatpak apps
files/
  scripts/            # scripts run during the build (e.g. branding.sh)
  system/             # everything here is copied into the root of the final system
tools/                # our own GUI tools (later)
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

## Custom ISO

The BlueBuild CLI can create an installer ISO from the finished image (`bluebuild generate-iso`). See https://blue-build.org
