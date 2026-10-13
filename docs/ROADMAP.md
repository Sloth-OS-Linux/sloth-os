# Sloth OS – terv

Alapelv: **ha a felhasználónak terminált kell nyitnia, az a mi hibánk.** A Konsole megmarad, de minden, amit
terminálból lehet csinálni, GUI-ból is menjen.

## 0. fázis – Alap image ✅ (ez a repó)
- [x] Universal Blue Kinoite alap, AMD/Intel + NVIDIA változat
- [x] Átnevezés (os-release)
- [x] Gaming csomagok: gamescope, mangohud, gamemode
- [x] Előtelepítve csak a Steam; minden más appot a felhasználó választ az üdvözlő varázslóban (a Firefox RPM is kikerül)
- [x] Első sikeres build GitHub Actionsben (mindkét image)
- [ ] Teszt VM-ben és a saját gépen

## 1. fázis – Saját arc
- [x] Logó: matt ezüst lajhár-arc, körvonal nélkül (`files/system/usr/share/sloth-os/logo/`, forrás: `docs/branding/`)
- [x] Boot animáció (Plymouth): a logó szélén körbefutó fehér pont (`files/system/usr/share/plymouth/themes/sloth-os/`, előnézet: `docs/branding/boot-preview.gif`; VM-ben még tesztelni)
- [x] Boot menü elrejtése (csak hibás indítás után jelenik meg) és csendes boot (`sloth-hide-boot-menu.service`, kargs; VM-ben még tesztelni)
- [ ] Háttérképek (a színtémákhoz illően)
- [x] Windows-szerű alapértelmezett Plasma-elrendezés: tálca alul, start menü a logóval, rögzített appok; bejelentkezés utáni betöltőképernyő a boot animációval (`files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/`; VM-ben még tesztelni)
- [ ] Más elrendezések választhatóan az üdvözlő varázslóban (pl. Windows 11-es középre igazított tálca, macOS-szerű dokk)
- [x] Színtémák: Silver sötét (alapértelmezett) és világos, Hófehér, Éjfekete, Ködkék, Éjkék, Zsálya (`tools/branding/gen_colors.py`, előnézet: `docs/branding/color-schemes-preview.png`)
- [ ] Saját Plasma téma (panel, ablakkeret)
- [ ] Bejelentkező képernyő (SDDM / Plasma Login) a Sloth OS kinézettel
- [ ] Ellenőrizni, hol látszik még "Fedora" vagy "Universal Blue" név (bejelentkezés, Rendszerinformáció, boot menü)

## 2. fázis – Gaming, ami csak működik
- [x] umu-launcher beépítése (a hivatalos GitHub RPM, rögzített verzió + SHA256: `files/scripts/umu-launcher.sh`)
- [x] **.exe kezelő** (`files/system/usr/lib/sloth-os/sloth-exe/`; VM-ben még tesztelni): dupla kattintás egy .exe/.msi-re →
  telepítés (programonként külön mappa, a parancsikonok a Start menübe) vagy indítás; első alkalommal az összetevők
  letöltése folyamatjelzővel. A felhasználó soha nem látja a "Wine", "Proton" vagy "prefix" szót.
  - [x] Telepített Windows-programok listája és eltávolítása a Sloth Központban
  - [ ] Hátravan: javítás (újratelepítés), parancsikon utólagos hozzáadása
  - [ ] Játékonkénti javítások automatikusan (umu adatbázis: GAMEID a program neve alapján)
- [x] Steamben a Proton alapból bekapcsolva minden játékra (`sloth-steam-proton-default.service`; VM-ben még tesztelni)
- [x] MangoHud / gamescope Flatpak Vulkan rétegek a Steam Flatpakhoz (`sloth-steam-vulkan-layers.timer`; VM-ben még tesztelni)
- [ ] Érthető hibaüzenet, ha egy játék anti-cheat miatt nem futhat Linuxon

## 3. fázis – Saját GUI eszközök
Cél: **minden terminálos feladatnak legyen grafikus megfelelője.** Ahol a KDE-nek már van jó GUI-ja, azt használjuk
(és ellenőrizzük, hogy előtelepített); ahol nincs, azt a saját eszközeink pótolják (Python + PySide6/QML,
jogosultságot igénylő műveletek polkiten keresztül, jelszókérő ablakkal).

### Saját eszközök
- [x] **Üdvözlő varázsló** első bejelentkezéskor (`files/system/usr/lib/sloth-os/sloth-welcome/`; VM-ben még tesztelni):
  színtéma, majd kategóriánként külön lépésben böngésző, irodai programok, zene és videó, csevegés, játékok,
  alkotás (benne az ArtCraft). Alapból semmi nincs bejelölve; telepítés folyamatjelzővel, hálózati hibánál
  újrapróbálkozás; a böngésző a tálcára kerül.
  - [ ] Hátravan: nyelv és fiókok, Steam-bejelentkezés, tálca-elrendezés választás
  - [ ] Az ArtCraft frissítése (GitHub-csomagként települ, a Flathub nem frissíti): saját frissítő
- [ ] **Sloth Központ** (egy app, modulokra bontva; `files/system/usr/lib/sloth-os/sloth-center/`):
  - [x] Frissítések és visszaállítás (keresés, telepítés folyamatjelzővel, újraindítás, vissza az előzőre; VM-ben még tesztelni). Hátravan: verzió megtartása (pin): verziók listája, „vissza az előzőre”, verzió megtartása (`rpm-ostree status/rollback/deploy --pin`)
  - [ ] Driverek és hardver: GPU, NVIDIA ↔ AMD/Intel image váltás (`rpm-ostree rebase`), Secure Boot kulcs regisztrálása (`mokutil`), kontrollerek
  - [ ] Rendszercsomagok (haladó): RPM rétegezés és eltávolítás (`rpm-ostree install/uninstall/reset`)
  - [ ] Rendszerindítás (haladó): kernelparaméterek (`rpm-ostree kargs`)
  - [x] Szolgáltatások: gyakoriak érthető névvel és kapcsolóval, haladó lista indítás/leállítással (`systemctl`). Hátravan: felhasználói szolgáltatások
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
