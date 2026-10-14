# Sloth OS – útmutató Claude Code-nak

## Mi ez
Egy Fedora Atomic alapú, Universal Blue `kinoite-main` / `kinoite-nvidia` image-re épülő desktop disztró,
BlueBuild-del építve. Cél: Windows-alternatíva átlagfelhasználóknak, erős gaming-támogatással.
A projekt nyelve magyar (kommentek, dokumentáció, UI szövegek); a kód azonosítói angolul.
Kivétel: **minden README angolul** készül (a repó később publikus lesz).

## Alapelvek
- **A felhasználónak soha ne kelljen terminál.** A Konsole elérhető marad, de bármit, amit valaki a terminálban
  csinálna (bármilyen és bármennyi beállítás), annak GUI-ból is mennie kell. Ha valami csak parancssorból megy, az bug.
  Ez a fejlesztői teendőkre is vonatkozik (repó, kulcsok, build, tesztelés). A lefedettség listája: `docs/ROADMAP.md`, 3. fázis.
- **Folyamat közben se látszódjon terminál.** Telepítés, frissítés, betöltés: folyamatjelző és emberi nyelvű
  állapotszöveg (pl. „Steam telepítése… 45%”), soha nem nyers parancssori kimenet. Bootkor nincs GRUB menü
  (csak hibás indítás után) és nincs szöveges kimenet, csak a Plymouth animáció.
- **Nem Bazzite.** Ne használj Bazzite image-et vagy Bazzite-specifikus eszközt (ujust receptek, bazzite-* csomagok) alapként.
- **A Proton/Wine legyen láthatatlan.** A felhasználó ne lássa a "Wine", "prefix", "Proton verzió" fogalmakat, hacsak nem kéri kifejezetten.
- **Az `ID=fedora` marad** az `/usr/lib/os-release`-ben; csak a megjelenített nevek változnak (lásd `files/scripts/branding.sh`).
- **Felhasználói appok Flatpakként**; RPM csak rendszerszintű dolgokhoz (`recipes/gaming.yml` stb.).
  Előtelepített app nincs, a Steam sem: mindent a felhasználó választ a Sloth Üdvözlőben
  (`files/system/usr/lib/sloth-os/sloth-welcome/sloth_welcome/catalog.py`). Alapból semmi nincs bejelölve,
  és a tálcára is csak az kerül, amit a felhasználó telepített.
- **Windows-programok Steam nélkül is futnak** (.exe kezelő): umu-launcher + Proton, amit a háttérben előre
  letöltünk; tartalékként a rendszer Wine-ja (`wine-core`), így internet nélkül is elindul egy .exe.
- Minden változás a recipe-ken és a `files/` mappán keresztül történik. A futó rendszeren kézzel semmit nem állítunk.

## Felépítés
- `recipes/recipe.yml`, `recipes/recipe-nvidia.yml`: a két image; a közös modulokat `from-file`-lal húzzák be.
- `recipes/branding.yml`, `gaming.yml`, `apps.yml`: modul-listák témánként.
- `files/system/`: a kész rendszer gyökerébe másolódik.
- `files/scripts/`: build közben futó scriptek (`type: script` modul).
- `files/system/usr/lib/sloth-os/<eszköz>/`: saját GUI eszközök (Python + PySide6/QML); `tools/`: fejlesztői segédek (nem kerülnek az image-be).
- `files/system/usr/lib/sloth-os/common/sloth_common/`: az eszközök közös részei (fordítások: eszközönként `translations/<nyelv>.json`, ellenőrzés: `tools/check_translations.py`).
- `iso/`: a telepítő ISO élő rendszere és a saját Sloth OS telepítő (csak az ISO-ba kerül, a telepített rendszerbe nem). Építés: `tools/build-iso.sh` (Linux) vagy `tools/build-iso.ps1` (Windows).
- `docs/ROADMAP.md`: a terv. Ha egy feladat kész, pipáld ki.

## Hasznos tudnivalók
- BlueBuild dokumentáció és modulok: https://blue-build.org
- Recipe séma: https://schema.blue-build.org/recipe-v1.json
- Helyi build (ha telepítve van a bluebuild CLI): `bluebuild build recipes/recipe.yml`
- A CI a `.github/workflows/build.yml`-ben fut; mindkét recipe-t buildeli.
- Új dnf csomag felvétele előtt ellenőrizd, hogy létezik-e a Fedora repóban az aktuális verzión.
