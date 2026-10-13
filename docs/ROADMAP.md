# Sloth OS – terv

Alapelv: **ha a felhasználónak terminált kell nyitnia, az a mi hibánk.** A Konsole megmarad, de minden, amit
terminálból lehet csinálni, GUI-ból is menjen.

## 0. fázis – Alap image ✅ (ez a repó)
- [x] Universal Blue Kinoite alap, AMD/Intel + NVIDIA változat
- [x] Átnevezés (os-release)
- [x] Gaming csomagok: gamescope, mangohud, gamemode
- [x] Előtelepített Flatpakok: Steam, Heroic, Discord, VLC, LibreOffice
- [x] Első sikeres build GitHub Actionsben (mindkét image)
- [ ] Teszt VM-ben és a saját gépen

## 1. fázis – Saját arc
- [x] Logó: matt ezüst lajhár-arc, körvonal nélkül (`files/system/usr/share/sloth-os/logo/`, forrás: `docs/branding/`)
- [x] Boot animáció (Plymouth): a logó szélén körbefutó fehér pont (`files/system/usr/share/plymouth/themes/sloth-os/`, előnézet: `docs/branding/boot-preview.gif`; VM-ben még tesztelni)
- [ ] Háttérképek (a színtémákhoz illően)
- [ ] Windows-szerű alapértelmezett Plasma-elrendezés (tálca alul, start menü, tálcaikonok)
- [x] Színtémák: Silver sötét (alapértelmezett) és világos, Hófehér, Éjfekete, Ködkék, Éjkék, Zsálya (`tools/branding/gen_colors.py`, előnézet: `docs/branding/color-schemes-preview.png`)
- [ ] Saját Plasma téma (panel, ablakkeret), Kickoff ikon a logóval
- [ ] Ellenőrizni, hol látszik még "Fedora" vagy "Universal Blue" név (bejelentkezés, Rendszerinformáció, boot menü)

## 2. fázis – Gaming, ami csak működik
- [ ] umu-launcher beépítése (nincs a Fedora repóban; a Heroic saját maga hozza, a .exe kezelőhöz kell megoldás)
- [ ] **.exe kezelő:** duplakattintás egy .exe-re → automatikus prefix, Proton verzió, javítások. A felhasználó soha nem látja a "Wine" vagy a "prefix" szót.
- [x] Steamben a Proton alapból bekapcsolva minden játékra (`sloth-steam-proton-default.service`; VM-ben még tesztelni)
- [x] MangoHud / gamescope Flatpak Vulkan rétegek a Steam Flatpakhoz (`sloth-steam-vulkan-layers.timer`; VM-ben még tesztelni)
- [ ] Érthető hibaüzenet, ha egy játék anti-cheat miatt nem futhat Linuxon

## 3. fázis – Saját GUI eszközök
Cél: **minden terminálos feladatnak legyen grafikus megfelelője.** Ahol a KDE-nek már van jó GUI-ja, azt használjuk
(és ellenőrizzük, hogy előtelepített); ahol nincs, azt a saját eszközeink pótolják (Python + PySide6/QML,
jogosultságot igénylő műveletek polkiten keresztül, jelszókérő ablakkal).

### Saját eszközök
- [ ] **Üdvözlő varázsló** első indításkor: nyelv, fiókok, Steam-bejelentkezés, ajánlott appok, színtéma választás
- [ ] **Sloth Központ** (egy app, modulokra bontva):
  - [ ] Frissítések és visszaállítás: verziók listája, „vissza az előzőre”, verzió megtartása (`rpm-ostree status/rollback/deploy --pin`)
  - [ ] Driverek és hardver: GPU, NVIDIA ↔ AMD/Intel image váltás (`rpm-ostree rebase`), Secure Boot kulcs regisztrálása (`mokutil`), kontrollerek
  - [ ] Rendszercsomagok (haladó): RPM rétegezés és eltávolítás (`rpm-ostree install/uninstall/reset`)
  - [ ] Rendszerindítás (haladó): kernelparaméterek (`rpm-ostree kargs`)
  - [ ] Szolgáltatások: be/ki kapcsolás, állapot (`systemctl`, rendszer és felhasználói)
  - [ ] Rendszer egészség: „Mi a baj?” nézet a logokból, emberi nyelven (`journalctl`)
  - [ ] Lemezek: tárhely-használat, lemezellenőrzés (`df`, `smartctl`)
  - [ ] Fejlesztői környezetek: Distrobox konténerek létrehozása, appok exportálása a menübe (`distrobox`)
  - [ ] Környezeti változók és indítási beállítások (`~/.config/environment.d`)
  - [ ] Haladó beállítások: minden olyan rendszerbeállítás, amire nincs KDE-s GUI (folyamatosan bővül)
- [ ] **Játékok:** játékonkénti beállítások (FPS-kijelző, felskálázás, teljesítmény-mód) Proton/Wine szavak nélkül

### Meglévő KDE / Flatpak GUI-k (ellenőrizni, hogy benne vannak-e az image-ben)
- [ ] Appok és frissítések: Discover · Flatpak jogosultságok: Rendszerbeállítások
- [ ] Tűzfal (`firewall-cmd`): Rendszerbeállítások tűzfal modul
- [ ] Partíciók (`fdisk`, `mkfs`): KDE Partíciókezelő
- [ ] Folyamatok (`top`, `kill`): Rendszerfigyelő
- [ ] Hálózat, VPN, nyomtatók, felhasználók, gépnév: Rendszerbeállítások

### Fejlesztői pult (a Sloth OS fejlesztéséhez)
- [ ] Repó és aláíró kulcs beállítása egy varázslóban (`gh`, `cosign`, GitHub secret)
- [ ] Build indítása és állapota, logok, Actions-perc felhasználás (`gh run`)
- [ ] Kipróbálás: VM indítása / tesztgép átállítása egy image-re (`rpm-ostree rebase`, privát registry bejelentkezés)

## 4. fázis – Kiadás
- [ ] Repó publikussá tétele, napi automatikus build visszakapcsolása (`.github/workflows/build.yml`)
- [ ] Telepítő ISO
- [ ] Weboldal, letöltés, dokumentáció
