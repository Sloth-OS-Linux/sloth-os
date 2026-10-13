# Sloth OS 🦥

Napi használatra és gamingre szánt Linux desktop, amit egy átlagos felhasználó úgy tud használni, mint a Windowst: **terminál nélkül**.

- **Alap:** Universal Blue `kinoite-main` / `kinoite-nvidia` (Fedora Atomic + KDE Plasma)
- **Frissítés:** atomic, a háttérben; ha valami elromlik, a boot menüben visszaállsz az előző verzióra
- **Appok:** Flatpak (Flathub)
- **Build:** [BlueBuild](https://blue-build.org) + GitHub Actions; minden commit után új image készül

## Felépítés

```
recipes/
  recipe.yml          # AMD / Intel image
  recipe-nvidia.yml   # NVIDIA image
  branding.yml        # név, logók, alapbeállítások
  gaming.yml          # gamescope, mangohud, gamemode...
  apps.yml            # előtelepített Flatpak appok
files/
  scripts/            # build közben futó scriptek (pl. branding.sh)
  system/             # ami ide kerül, az a kész rendszer gyökerébe másolódik
tools/                # a saját GUI eszközök (később)
docs/ROADMAP.md       # a terv
```

## Első beállítás (egyszer kell)

1. Hozz létre egy **publikus** GitHub repót `sloth-os` néven, és töltsd fel ezt a mappát.
2. Generálj aláíró kulcsot a repó mappájában (a jelszót hagyd üresen):
   ```
   cosign generate-key-pair
   ```
3. A GitHubon: **Settings → Secrets and variables → Actions → New repository secret**
   - Név: `SIGNING_SECRET`
   - Érték: a `cosign.key` fájl teljes tartalma
4. A `cosign.pub` fájlt commitold. A `cosign.key` **soha** ne kerüljön fel (a `.gitignore` ezt kizárja).
5. Push után az **Actions** fül alatt elindul a build. Ha végzett, a **Packages** alatt megjelenik a `sloth-os` és a `sloth-os-nvidia` image.

## Kipróbálás (VM-ben vagy tesztgépen)

Telepíts egy sima **Fedora Kinoite**-ot, majd:

```
# 1. lépés: átállás az image-re (még aláírás-ellenőrzés nélkül)
rpm-ostree rebase ostree-unverified-registry:ghcr.io/bathorizsolt/sloth-os:latest
systemctl reboot

# 2. lépés: átállás az aláírt változatra
rpm-ostree rebase ostree-image-signed:docker://ghcr.io/bathorizsolt/sloth-os:latest
systemctl reboot
```

NVIDIA gépen ugyanez a `sloth-os-nvidia` névvel.

> Ez a fejlesztői út. A végfelhasználók később egy saját telepítő ISO-t kapnak, és soha nem látnak ilyen parancsot.

## Saját ISO

A BlueBuild CLI tud telepítő ISO-t készíteni a kész image-ből (`bluebuild generate-iso`). Lásd: https://blue-build.org
