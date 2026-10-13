# Sloth OS – terv

Alapelv: **ha a felhasználónak terminált kell nyitnia, az a mi hibánk.**

## 0. fázis – Alap image ✅ (ez a repó)
- [x] Universal Blue Kinoite alap, AMD/Intel + NVIDIA változat
- [x] Átnevezés (os-release)
- [x] Gaming csomagok: gamescope, mangohud, gamemode
- [x] Előtelepített Flatpakok: Steam, Heroic, Discord, VLC, LibreOffice
- [ ] Első sikeres build GitHub Actionsben
- [ ] Teszt VM-ben és a saját gépen

## 1. fázis – Saját arc
- [x] Logó: matt ezüst lajhár-arc, körvonal nélkül (`files/system/usr/share/sloth-os/logo/`, forrás: `docs/branding/`)
- [ ] Boot animáció (Plymouth), háttérképek
- [ ] Windows-szerű alapértelmezett Plasma-elrendezés (tálca alul, start menü, tálcaikonok)
- [x] Saját színséma: Sloth Silver sötét (alapértelmezett) és világos (`files/scripts/theme.sh`)
- [ ] Saját Plasma téma (panel, ablakkeret), Kickoff ikon a logóval
- [ ] Ellenőrizni, hol látszik még "Fedora" vagy "Universal Blue" név (bejelentkezés, Rendszerinformáció, boot menü)
- [ ] A Konsole elrejtése a menüből ("fejlesztői mód" kapcsolóval visszahozható)

## 2. fázis – Gaming, ami csak működik
- [ ] umu-launcher beépítése (nincs a Fedora repóban; a Heroic saját maga hozza, a .exe kezelőhöz kell megoldás)
- [ ] **.exe kezelő:** duplakattintás egy .exe-re → automatikus prefix, Proton verzió, javítások. A felhasználó soha nem látja a "Wine" vagy a "prefix" szót.
- [x] Steamben a Proton alapból bekapcsolva minden játékra (`sloth-steam-proton-default.service`; VM-ben még tesztelni)
- [x] MangoHud / gamescope Flatpak Vulkan rétegek a Steam Flatpakhoz (`sloth-steam-vulkan-layers.timer`; VM-ben még tesztelni)
- [ ] Érthető hibaüzenet, ha egy játék anti-cheat miatt nem futhat Linuxon

## 3. fázis – Saját GUI eszközök
- [ ] **Üdvözlő varázsló** első indításkor: nyelv, fiókok, Steam-bejelentkezés, ajánlott appok
- [ ] **Rendszer egészség:** "Mi a baj?" nézet a logokból, emberi nyelven
- [ ] **Frissítések és visszaállítás:** egy gomb, ami az előző verzióra áll vissza
- [ ] **Driverek és hardver:** GPU, kontrollerek, nyomtatók

## 4. fázis – Kiadás
- [ ] Repó publikussá tétele, napi automatikus build visszakapcsolása (`.github/workflows/build.yml`)
- [ ] Telepítő ISO
- [ ] Weboldal, letöltés, dokumentáció
