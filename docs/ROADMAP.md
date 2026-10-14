# Sloth OS – terv

Alapelv: **ha a felhasználónak terminált kell nyitnia, az a mi hibánk.** A Konsole megmarad, de minden, amit
terminálból lehet csinálni, GUI-ból is menjen.

## Hol tartunk (2026-10-14)
- Második VM-teszt (első saját ISO, 6,8 GB): rejtett GRUB, szöveg nélküli boot, Firefox a tálcán, nyelvváltás
  a választón azonnal: rendben. A telepítés nem ment végig; a talált hibák javítva (4. fázis, „Saját telepítő”),
  de VM-ben még újra kell nézni. Következő lépés: új ISO (`tools/build-iso.sh` Linuxon, `tools/build-iso.ps1`
  Windowson; kell a GitHub CLI `read:packages` joga), majd VM-teszt végig: telepítés, első indítás, Üdvözlő.
- Utána: a Sloth Központ nyitott pontjai és fordítása a maradék 48 nyelvre (a kód már fordítható, a magyar és
  az angol kész; hiányzók listája: `python tools/extract_center_strings.py <nyelv>`), majd a Windows mellé telepítés.

## 0. fázis – Alap image ✅ (ez a repó)
- [x] Universal Blue Kinoite alap, AMD/Intel + NVIDIA változat
- [x] Átnevezés (os-release)
- [x] Gaming csomagok: gamescope, mangohud, gamemode
- [x] Nincs előtelepített app, a Steam sem: mindent a felhasználó választ az üdvözlő varázslóban (a Firefox RPM is kikerül);
  a tálcára is csak az kerül, amit telepített
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
  - [x] A KDE üdvözlő appja (`plasma-welcome`) kikerül az image-ből (`files/scripts/remove-default-apps.sh`), a Sloth
    Üdvözlő fut helyette. A korábbi `kded6rc`-s kikapcsolás nem működött (az élő rendszerben eltakarta a telepítőt)
  - [x] Alapértelmezett háttérkép: a saját Sloth OS háttérkép
  - [x] Firmware (BIOS/UEFI) boot-bejegyzés neve: a saját telepítő „Sloth OS”-re nevezi át (egy `lsblk`-hiba miatt
    eddig nem futott le, javítva; VM-ben még tesztelni)
  - [ ] VM-ben végignézni: bejelentkező képernyő, Discover, Rendszerbeállítások

## 2. fázis – Gaming, ami csak működik
- [x] umu-launcher beépítése (a hivatalos GitHub RPM, rögzített verzió + SHA256: `files/scripts/umu-launcher.sh`)
- [x] Windows-programok Steam nélkül és internet nélkül is: a Protont bejelentkezés után a háttérben előre letöltjük
  és frissen tartjuk (`sloth-windows-prepare.timer`); ha még nincs meg és nincs net, a rendszer Wine-ja indítja
  (`wine-core`, `wine-dxvk`, `wine-mono`; `sloth_exe/backend.py`). VM-ben még tesztelni
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
    az első lapon átváltható. Hátravan: anyanyelvi átnézés (a fordításokat MI készítette), a Sloth Központ
    fordítása a maradék 48 nyelvre (magyar és angol kész)
  - [x] A végén gyors gombok: Steam-bejelentkezés, online fiókok, nyelv és régió (a nyelvet a telepítő kérdezi)
  - [x] Az ArtCraft frissítése: felhasználói telepítés + napi háttérfrissítő (`sloth-github-bundle-update.timer`, SHA256 ellenőrzéssel); VM-ben még tesztelni
- [ ] **Sloth Központ** (egy app, modulokra bontva; `files/system/usr/lib/sloth-os/sloth-center/`):
  - [x] Frissítések és visszaállítás (keresés, telepítés folyamatjelzővel, újraindítás, vissza az előzőre, a mostani verzió megtartása; VM-ben még tesztelni);
    a gépen lévő összes verzió listája: bármelyik indítható legközelebb letöltés nélkül (`ostree admin set-default`),
    és egyenként megtartható
  - [x] Driverek és hardver: videókártya felismerése, NVIDIA ↔ AMD/Intel változat váltása (`rpm-ostree rebase`),
    Secure Boot kulcs regisztrálása lépésenkénti útmutatóval (`mokutil`); VM-ben és Secure Boot-os gépen még tesztelni.
    Kontrollerek: a csatlakoztatottak listája (kábel / Bluetooth, akkuszint), párosítás és a gombok kipróbálása
    a KDE moduljaival. Megjegyzés: amíg a repó privát, a váltáshoz registry-bejelentkezés kell (Fejlesztői pult)
  - [x] Közös rendszergazdai segéd (`/usr/libexec/sloth-os/sloth-helper` + polkit `org.slothos.helper`): rögzített műveletek, grafikus jelszókérővel
  - [x] Jelszókérő nélküli rendszergazda (Sloth Központ → Fiók és biztonság, és egyszerűsítve az Üdvözlő „Jelszavak”
    lépésében): témakörönként polkit-szabály (`/etc/polkit-1/rules.d/49-sloth-admin.rules`, forrás:
    `/etc/sloth-os/admin-policy.json`, a `sloth-helper admin-policy` írja, mindig csak a hívó felhasználóra),
    sudo jelszó nélkül (`/etc/sudoers.d`), automatikus bejelentkezés (Plasma Login Manager). VM-ben még tesztelni
    (`pkcheck`). Hátravan: a jelszótároló (KWallet) automatikus nyitása automatikus bejelentkezésnél; a rendszergazdai
    jog a KDE Felhasználók moduljában állítható. Az eredeti terv:
  - Jelszókérő nélküli rendszergazda: fiók létrehozásakor (telepítő / első indítás) választható, hogy a felhasználó
    rendszergazda-e, és ha igen, kérjen-e jelszót a rendszergazdai műveleteknél. Ha nem kér, minden kérdés nélkül
    lefut (polkit-szabály a felhasználóra vagy egy külön csoportra, pl. `/etc/polkit-1/rules.d/`, + sudo NOPASSWD).
    Ne csak „mindenhez / semmihez”: témakörönként választható legyen, mihez kell jelszó (programok telepítése,
    frissítés, hálózat és eszközök, dátum és nyelv, szolgáltatások és driverek, lemezek, felhasználók és jelszavak,
    rendszerindítás és rendszercsomagok; az utolsó hármat alapból védjük), plusz automatikus bejelentkezés,
    jelszótároló (KWallet) automatikus nyitása, jelszó a terminálban (sudo). Utólag a Sloth Központban is
    átállítható legyen, terminál nélkül
  - [ ] Bejelentkezési módok a hardver alapján (varázsló + Sloth Központ; a gép felismeri, mit tud, és csak azt kínálja fel):
    jelszó; PIN-kód 4/6/8 számjeggyel (saját PAM-modul, csak a gépen tárolt hash, lehetőleg TPM-mel, sikertelen
    próbálkozások után várakozás); ujjlenyomat (`fprintd`, ha van támogatott olvasó); arcfelismerés (Howdy, csak
    infrakamerával, mint a Windows Hello; nincs a Fedora repóban); céges fiók (Active Directory: `realmd` + `sssd`,
    tartományhoz csatlakozás GUI-ból; később Entra ID); biztonsági kulcs (FIDO2/YubiKey, `pam_u2f`).
    Telefonos passkey helyi bejelentkezéshez Linuxon most még nincs kész megoldás, figyelni.
    Megjegyzés: PIN, ujjlenyomat vagy arc esetén a jelszótároló (KWallet) nem nyílik ki magától, ezt meg kell oldani
  - [x] Rendszercsomagok (haladó): RPM rétegezés és eltávolítás (`rpm-ostree install/uninstall`)
  - [x] Rendszerindítás (haladó): kernelparaméterek (`rpm-ostree kargs`), boot menü mutatása dual boothoz
  - [x] Szolgáltatások: gyakoriak érthető névvel és kapcsolóval, haladó lista indítás/leállítással (`systemctl`);
    a felhasználó saját szolgáltatásai jelszó nélkül (`systemctl --user`), a munkamenet alapjai védettek
  - [x] Rendszer egészség: „Mi a baj?” nézet emberi nyelven (tárhely, el nem indult szolgáltatások, összeomlások, memóriahiány, videókártya- és lemezhibák, hőmérséklet), napló mentése segítségkéréshez (`journalctl`)
  - [x] Lemezek: meghajtók foglaltsága, egészsége (SMART) és hőmérséklete, felesleges app-összetevők törlése (`df`, `smartctl`, `flatpak uninstall --unused`)
  - [x] Fejlesztői környezetek: dobozok (Ubuntu, Debian, Arch, Fedora) létrehozása és törlése, programok telepítése a dobozba, appok a Start menübe (`distrobox`); VM-ben még tesztelni
  - [x] Környezeti változók és indítási beállítások (Haladó beállítások): saját változók a
    `~/.config/environment.d`-ben jelszó nélkül, a többi program változói megjelenítve, a kockázatosak
    (pl. `PATH`) megjelölve; bejelentkezéskor induló programok: a KDE Automatikus indítás modulja
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
- [ ] **Saját Sloth OS telepítő** (`iso/`): élő rendszer a pendrive-ról, kipróbálás telepítés nélkül, Anaconda nélkül
  - [x] Első változat: nyelv (az Üdvözlő 50 nyelve), billentyűzet, időzóna, egész lemezre telepítés
    (saját particionálás + `bootc install to-filesystem`, az image az ISO-ban van, internet nélkül is megy),
    folyamatjelző, újraindítás; a fiókot első induláskor a KDE Plasma Setup hozza létre. Építés:
    `tools/build-iso.sh` (Linux) vagy `tools/build-iso.ps1` (Windows), helyben Podmannel, vagy `.github/workflows/iso.yml`
  - [x] A telepítő mind az 50 nyelven
  - [x] Teljes képernyős „Kipróbálom / Telepítem” választó; kipróbáláshoz Firefox az élő rendszerben, és ha
    telepítéskor nincs internet, a telepítő átmásolja (különben az Üdvözlőben választ a felhasználó)
  - [x] Rejtett GRUB az ISO-n (Escre jön elő); a firmware boot-bejegyzés neve „Sloth OS” (nem „Fedora”)
  - [x] Kisebb ISO: a telepítendő image kicsomagolva, a közös fájlok csak egyszer (cél kb. 5 GB); VM-ben még tesztelni
  - [x] A második VM-teszt (2026-10-14) hibái javítva, VM-ben újra megnézni:
    - a telepítés 4 GB RAM-mal elfogyott (a `bootc` a rétegeket a RAM-ban lévő `/var/tmp`-be csomagolta ki):
      most a lemez végén egy átmeneti munkapartíciót használ, amit utána a rendszerpartícióhoz csatol;
    - a telepítés végén nem találta a gyökérpartíciót, és a boot-bejegyzést sem nevezte át (`lsblk --json`
      `--tree` nélkül lapos listát ad); a folyamatjelző 36%-on állt a másolás alatt (most a lemezre írt adatból halad);
    - a KDE üdvözlője eltakarta a telepítőt; a választott billentyűzet az élő rendszerben nem állt át
      (a próbamező így semmit nem mutatott; most `kwriteconfig6 --notify`, és a KWin nem a locale1-et követi);
    - billentyűzettel: a lenyitott listákban nem működtek a nyilak, nem látszott a fókusz; a lemez neve
      „0x1af4” volt (most gyártó, típus, HDD/SSD/NVMe)
  - [ ] Windows mellé telepítés: a Windows-partíció zsugorítása, közös boot menü, BitLocker felismerése és magyarázata
  - [ ] NVIDIA-s gépen automatikusan az NVIDIA-s változat (most a Sloth Központban lehet utána váltani)
  - [ ] Telepítés után a frissítések aláírás-ellenőrzéssel (`ostree-image-signed`)
  - [ ] Lemeztitkosítás, régi (BIOS-os) gépek
  - [ ] Plasma Setup (első indítás) háttere a Sloth OS háttérkép
  - [ ] ISO letöltése: privát repóban a 2 GB-os kiadás- és 500 MB-os tárhelykorlát miatt csak publikussá tétel után
- [ ] Weboldal, letöltés, dokumentáció
