# Sloth OS – terv

Alapelv: **ha a felhasználónak terminált kell nyitnia, az a mi hibánk.** A Konsole megmarad, de minden, amit
terminálból lehet csinálni, GUI-ból is menjen.

## 0. fázis – Alap image ✅ (ez a repó)
- [x] Universal Blue Kinoite alap, AMD/Intel + NVIDIA változat
- [x] Átnevezés (os-release)
- [x] Gaming csomagok: gamescope, mangohud, gamemode
- [x] Előtelepítve csak a Steam; minden más appot a felhasználó választ az üdvözlő varázslóban (a Firefox RPM is kikerül)
- [x] Első sikeres build GitHub Actionsben (mindkét image)
- [ ] Teszt VM-ben és a saját gépen. Első VM-teszt (2026-10-13), eredmények:
  - [x] Rejtett boot menü, Plymouth animáció, „Sloth OS” név (TTY, gépnév, Plasma Setup „A gépházban: Sloth OS”)
  - [x] Sloth Üdvözlő elindul teljes képernyőn; színtéma-váltás azonnal működik; tálca-elrendezés választható; mind a 6 kategória megjelenik
  - [ ] Appok telepítése a varázslóból (a teszt-proxy hibája miatt még nem futott le)
  - [x] Javítva: a „Csevegés” kategória ikonja hiányzott (`internet-chat` nincs a Breeze-ben; most `kopete`, tartalék `dialog-messages`)
  - [x] Javítva: az appkártyákon a nem kijelölt is pipát mutatott (a Breeze-ben nincs `checkbox-unchecked`, helyette a bepipált `checkbox` jött); most valódi jelölőnégyzet és erősebb kiemelés
  - [x] Javítva: a színtéma-kártyák soronként középre igazítva, egyenletesen elosztva (7 kártya: 4 + 3)
  - [ ] Asztal, tálca, Sloth Központ, .exe kezelő, boot közbeni betöltőképernyő még nincs megnézve
  - [x] Javítva: a Sloth Központ nem nyílt meg (`NameError` a Frissítések modul betöltésekor); VM-ben újra megnézni
  - [x] Javítva: az indítóprogramos Windows-appok (pl. Battle.net) elindulás után bezáródtak (`PROTON_VERB=run`
    helyett mindig `waitforexitandrun`); VM-ben újra megnézni
  - Megjegyzés: a szöveges kickstart telepítés `multi-user.target`-et állít be (kell: `xconfig --startxonboot`),
    és ha a telepítő nem hoz létre `/etc/plasma-setup-done`-t, a KDE Plasma Setup varázslója jön elő

## 1. fázis – Saját arc
- [x] Logó: matt ezüst lajhár-arc, körvonal nélkül (`files/system/usr/share/sloth-os/logo/`, forrás: `docs/branding/`)
- [x] Boot animáció (Plymouth): a logó szélén körbefutó fehér pont (`files/system/usr/share/plymouth/themes/sloth-os/`, előnézet: `docs/branding/boot-preview.gif`; VM-ben még tesztelni)
- [x] Boot menü elrejtése (csak hibás indítás után jelenik meg) és csendes boot (`sloth-hide-boot-menu.service`, kargs; VM-ben még tesztelni)
- [x] Háttérképek: 16 kép 4K-ban (MI-felskálázással), az ultraszélesek 5120×2160-ban is; alapértelmezett: „Metallic Sloth Over Silver Waves” (asztal és zárolási képernyő)
- [x] Windows-szerű alapértelmezett Plasma-elrendezés: tálca alul, start menü a logóval, rögzített appok; bejelentkezés utáni betöltőképernyő a boot animációval (`files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/`; VM-ben még tesztelni)
- [x] Más elrendezések választhatóan az üdvözlő varázslóban: Windows 10, Windows 11 (középre igazított), macOS-szerű (felső sáv + lebegő dokk); VM-ben még tesztelni
- [x] Színtémák: Silver sötét (alapértelmezett) és világos, Hófehér, Éjfekete, Ködkék, Éjkék, Zsálya (`tools/branding/gen_colors.py`, előnézet: `docs/branding/color-schemes-preview.png`)
- [ ] Saját Plasma téma (panel, ablakkeret)
- [x] Bejelentkező képernyő (Plasma Login Manager, tartalékként SDDM): Sloth OS háttérkép, Sloth Silver színek; VM-ben még tesztelni
- [ ] Ellenőrizni, hol látszik még "Fedora" vagy "Universal Blue" név. Eddig:
  - [x] Rendszerinformáció, boot menü bejegyzések, gépnév: az os-release-ből jönnek (Sloth OS)
  - [x] A KDE üdvözlő appja kikapcsolva (a Sloth Üdvözlő helyett ne jöjjön elő): `files/system/etc/xdg/kded6rc`
  - [x] Alapértelmezett háttérkép: a saját Sloth OS háttérkép
  - [ ] Firmware (BIOS/UEFI) boot-bejegyzés neve "Fedora": a telepítő hozza létre, a saját ISO-nál átnevezni
  - [ ] VM-ben végignézni: bejelentkező képernyő, Discover, Rendszerbeállítások

## 2. fázis – Gaming, ami csak működik
- [x] umu-launcher beépítése (a hivatalos GitHub RPM, rögzített verzió + SHA256: `files/scripts/umu-launcher.sh`)
- [x] **.exe kezelő** (`files/system/usr/lib/sloth-os/sloth-exe/`; VM-ben még tesztelni): dupla kattintás egy .exe/.msi-re →
  telepítés (programonként külön mappa, a parancsikonok a Start menübe) vagy indítás; első alkalommal az összetevők
  letöltése folyamatjelzővel. A felhasználó soha nem látja a "Wine", "Proton" vagy "prefix" szót.
  - [x] Telepített Windows-programok listája és eltávolítása a Sloth Központban
  - [x] Start menü bejegyzések utólagos szerkesztése (Sloth Központ → Windows-programok → Start menü)
  - [ ] Hátravan: javítás (újratelepítés)
  - [ ] Játékonkénti javítások automatikusan (umu adatbázis: GAMEID a program neve alapján)
- [x] Steamben a Proton alapból bekapcsolva minden játékra (`sloth-steam-proton-default.service`; VM-ben még tesztelni)
- [x] MangoHud / gamescope Flatpak Vulkan rétegek a Steam Flatpakhoz (`sloth-steam-vulkan-layers.timer`; VM-ben még tesztelni)
- [x] Érthető hibaüzenet, ha egy játék anti-cheat miatt nem futhat Linuxon (.exe kezelő: Vanguard, FACEIT, Ricochet… esetén rögtön szól; Easy Anti-Cheat / BattlEye esetén akkor, ha a játék gyorsan kilép). Hátravan: ugyanez a Steames játékoknál

## 3. fázis – Saját GUI eszközök
Cél: **minden terminálos feladatnak legyen grafikus megfelelője.** Ahol a KDE-nek már van jó GUI-ja, azt használjuk
(és ellenőrizzük, hogy előtelepített); ahol nincs, azt a saját eszközeink pótolják (Python + PySide6/QML,
jogosultságot igénylő műveletek polkiten keresztül, jelszókérő ablakkal).

### Saját eszközök
- [x] **Üdvözlő varázsló** első bejelentkezéskor (`files/system/usr/lib/sloth-os/sloth-welcome/`; VM-ben még tesztelni):
  színtéma, majd kategóriánként külön lépésben böngésző, irodai programok, zene és videó, csevegés, játékok,
  alkotás (benne az ArtCraft). Alapból semmi nincs bejelölve; telepítés folyamatjelzővel, hálózati hibánál
  újrapróbálkozás; a böngésző a tálcára kerül.
  - [x] Tálca-elrendezés választás
  - [x] Többnyelvű: a Fedora telepítő mind az 50 használható nyelvén (amelyeken az Anaconda legalább félig le van
    fordítva, plusz norvég bokmål), jobbról balra írással (arab, héber) és minden írásrendszerhez betűtípussal
    (`sloth_welcome/translations/*.json`, ellenőrzés: `tools/check_translations.py`); alapból a rendszer nyelvén indul,
    az első lapon átváltható. Hátravan: anyanyelvi átnézés (a fordításokat MI készítette), a Sloth Központ és
    a .exe kezelő fordítása
  - [x] A végén gyors gombok: Steam-bejelentkezés, online fiókok, nyelv és régió (a nyelvet a telepítő kérdezi)
  - [x] Az ArtCraft frissítése: felhasználói telepítés + napi háttérfrissítő (`sloth-github-bundle-update.timer`, SHA256 ellenőrzéssel); VM-ben még tesztelni
- [ ] **Sloth Központ** (egy app, modulokra bontva; `files/system/usr/lib/sloth-os/sloth-center/`):
  - [x] Frissítések és visszaállítás (keresés, telepítés folyamatjelzővel, újraindítás, vissza az előzőre, a mostani verzió megtartása; VM-ben még tesztelni). Hátravan: korábbi, megtartott verziók listája és visszaállítása (`rpm-ostree deploy`)
  - [x] Driverek és hardver: videókártya felismerése, NVIDIA ↔ AMD/Intel változat váltása (`rpm-ostree rebase`),
    Secure Boot kulcs regisztrálása lépésenkénti útmutatóval (`mokutil`); VM-ben és Secure Boot-os gépen még tesztelni.
    Hátravan: kontrollerek. Megjegyzés: amíg a repó privát, a váltáshoz registry-bejelentkezés kell (Fejlesztői pult)
  - [x] Közös rendszergazdai segéd (`/usr/libexec/sloth-os/sloth-helper` + polkit `org.slothos.helper`): rögzített műveletek, grafikus jelszókérővel
  - [x] Rendszercsomagok (haladó): RPM rétegezés és eltávolítás (`rpm-ostree install/uninstall`)
  - [x] Rendszerindítás (haladó): kernelparaméterek (`rpm-ostree kargs`), boot menü mutatása dual boothoz
  - [x] Szolgáltatások: gyakoriak érthető névvel és kapcsolóval, haladó lista indítás/leállítással (`systemctl`). Hátravan: felhasználói szolgáltatások
  - [x] Rendszer egészség: „Mi a baj?” nézet emberi nyelven (tárhely, el nem indult szolgáltatások, összeomlások, memóriahiány, videókártya- és lemezhibák, hőmérséklet), napló mentése segítségkéréshez (`journalctl`)
  - [x] Lemezek: meghajtók foglaltsága, egészsége (SMART) és hőmérséklete, felesleges app-összetevők törlése (`df`, `smartctl`, `flatpak uninstall --unused`)
  - [x] Fejlesztői környezetek: dobozok (Ubuntu, Debian, Arch, Fedora) létrehozása és törlése, programok telepítése a dobozba, appok a Start menübe (`distrobox`); VM-ben még tesztelni
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
- [ ] Telepítő ISO (privát repóban a 2 GB-os kiadás- és 500 MB-os tárhelykorlát miatt csak publikussá tétel után).
  Ötlet: Windows-szerű első indítás a KDE Plasma Setup-pal (fiók, nyelv, billentyűzet), utána a Sloth Üdvözlő;
  ehhez a Plasma Setup háttere legyen a Sloth OS háttérkép
- [ ] Weboldal, letöltés, dokumentáció
