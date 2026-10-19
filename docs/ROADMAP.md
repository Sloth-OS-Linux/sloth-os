# Sloth OS – terv

Alapelv: **ha a felhasználónak terminált kell nyitnia, az a mi hibánk.** A Konsole megmarad, de minden, amit
terminálból lehet csinálni, GUI-ból is menjen.

## Hol tartunk (2026-10-19)

### Fontos: a 2026-10-16-i teszt még a régi image-dzsel ment
A tesztelt ISO (`out/sloth-os.iso`) 2026-10-16 08:17-kor készült, amikor a registry `latest` címkéje még a
2026-10-15 22:31-es image-re (`35e4c9d`) mutatott. A 10-16-i javítások (lent) csak 11:33-kor kerültek a
`latest`-be; ezért látszott még „Sloth OS 44”, és ezért viselkedett a Battle.net a régi módon. **Új ISO
csak a mostani fejlesztések pusholása és a CI-build után.** A telepített gépen a futó változat: Sloth Központ →
Rendszer egészség → Napló mentése (az eleje most a futó image-et is mutatja).

### Elkészült 2026-10-19: egységes Windows-alkalmazáskezelés (a 2026-10-16 esti teszt kérései)
Egységtesztekkel (`tools/tests/test_apps.py`, Linuxon, Qt és Wine nélkül) és a Qt-s modulok betöltésével
kipróbálva, **valódi gépen még nem**.
- **Közös alkalmazáskönyvtár** (`sloth_common/apps/`: library, menu, winreg, detect, steam): a .exe kezelő és
  a Sloth Központ ugyanazt használja (a korábbi kettős mappaolvasás megszűnt)
- **Látható hely: `~/Applications/<program>/`**: `windows/` (a program Windows-környezete), `.sloth/app.json`
  (adatok), „Program fájljai” hivatkozás a telepített fájlokra, a mappa ikonja a Dolphinban. A hely a Sloth
  Központban állítható (csak Linuxos fájlrendszer; NTFS/exFAT/FAT-ra érthető üzenet), a programok
  áthelyezhetők (a Start menü bejegyzései érvényesek maradnak). A régi helyről
  (`~/.local/share/sloth-os/windows-programs`) egyszer, átnevezéssel költöznek át (a futó programok maradnak)
- **Felismerés telepítés után:** a registry „Uninstall” bejegyzéséből a valódi név („Battle.net”), kiadó,
  verzió, telepítési hely; az indító a parancsikonokból, a registry ikonjából vagy pontozott .exe-kből (a
  frissítők, hibajelentők, eltávolítók kiesnek; azonos név csak egyszer). A telepítés csak akkor kész, ha a
  program környezetében már semmi nem fut. Ha nem biztos: „Másik fájl…” tallózó. A végén „Indítás”
- **Már futó program:** nem indul újra („X már fut”); ha a környezetében más fut (pl. az indító, és egy játékot
  indít a felhasználó), ahhoz csatlakozik (`runinprefix`), nem vár a végéig
- **Sloth Központ → Windows-programok:** Indítás, Fájlok, Start menü, Javítás (a megjegyzett indítási
  beállítások törlése), Újratelepítés, Áthelyezés, „Program telepítése…”, a programok helye
- **Steam-átvétel:** a Steamhez kézzel hozzáadott Windows-programok (`shortcuts.vdf`) felvétele újratelepítés
  nélkül: „A Steamen keresztül” (csak bejegyzés, a Steam indítja) vagy „Átvétel” (reflink másolat a Steam
  környezetéről, onnan a Sloth indítja). A Steam fájljaihoz egyik sem nyúl; a Steam környezetét sosem indítjuk
  a saját futtatónkkal
- **Dolphin 128 TB:** a composefs (a rendszer csak olvasható képe, Fedora 42 óta) loop eszköze névtelen
  kötetként látszott; udev-szabály rejti el (`/usr/lib/udev/rules.d/90-sloth-udisks.rules`), a
  rendszerpartíció neve „Sloth OS”. Csak megjelenítés, a csatolásokhoz nem nyúl. Valódi gépen ellenőrizni
- **Napló mentése** (Rendszer egészség): az elején a futó image, a lemezek, a csatolások és a loop eszközök
- **Epic:** a 32 bites indító helyett a 64 bites kliens indul (mint a Lutrisban)
- **Fordítások:** az új szövegek mind az 50 nyelven

### Elkészült 2026-10-16 (a reggeli teszt hibái, részletek lent, „A reggeli teszt eredménye”)
Minden pusholva; szimulációval / egységtesztekkel kipróbálva, **valódi gépen még nem** (a 10-16-i ISO-ban még
nem volt benne, lásd fent).
- **Üdvözlő:** az appok egyesével, sorban települnek, összesített letöltési mérettel; a végén Újraindítás gomb;
  a tálca-ikonok frissítése bezáráskor
- **.exe kezelő:** egy programot csak egyszer telepít (Megnyitás / Újratelepítés); a Battle.net a klienssel indul
  (az indító kilépésével eddig a kliens is bezárult)
- **Steam első indítása:** Plasma-értesítés, amíg a Steam letölti magát
- **Verziószám:** „Sloth OS 1.0 (Fedora Atomic 44)”

### Következő teszt (új ISO a 2026-10-19-i változások CI-buildje után)
- [ ] **Üdvözlő:** 4–5 app egyszerre: sorban, egyesével települnek; a felirat csak „X telepítése…”, alatta
  „x MB / y MB”; nincs dupla sor; a végén Újraindítás, utána az ikonok a tálcán; Újraindítás nélkül is jók-e az ikonok
- [x] **Steam:** első indításkor jön-e az értesítés („A Steam első indítása”, „x MB letöltve”), eltűnik-e, amikor a
  Steam megnyílik; utána a `bootstrap_log.txt`. 2026-10-19: működik, jól írja ki
- [ ] **Battle.net:** telepítés, indítás a Start menüből; nyitva marad-e; bejelentkezés, egy játék telepítése és
  indítása; a Start menüben csak egy bejegyzés
- [ ] **.exe kezelő:** ugyanazt a telepítőt még egyszer megnyitva „már telepítve van”, a Megnyitás elindítja
- [ ] **Alkalmazáskönyvtár:** a Battle.net telepítés után a `~/Applications/Battle.net/` mappában van (a Dolphinban
  a program ikonjával, benne a „Program fájljai”); a neve „Battle.net” (nem „Battle Net”); a választólistán egy
  bejegyzés van bejelölve; az „Indítás” gomb elindítja. Egy telepítő, ami letöltőként kilép (pl. Battle.net,
  EA app): a .exe kezelő megvárja a tényleges telepítést. A háttérnapló: `~/.cache/sloth-os/apps/<program>/naplo/`
- [ ] **Már futó program:** a Battle.net futása közben a Start menüből újra elindítva „már fut”; egy játék indítása
  a Battle.net-ből (és ha van, a Start menüből) a Battle.net futása közben
- [ ] **Sloth Központ → Windows-programok:** Indítás, Fájlok, Start menü, Javítás, Áthelyezés (egy másik mappába,
  utána indul-e a Start menüből), a hely módosítása egy NTFS-es pendrive-ra (érthető üzenet), Eltávolítás
- [ ] **Steam-átvétel:** a Steamben kézzel hozzáadott Battle.net megjelenik „A Steamhez hozzáadott programok”
  között; „A Steamen keresztül” és „Átvétel” is; utána a Steamből is ugyanúgy indul
- [ ] **Átköltözés:** egy régi helyen (`~/.local/share/sloth-os/windows-programs`) lévő program a frissítés után a
  `~/Applications` alatt van, és a Start menüből indul
- [ ] **Dolphin:** az Eszközök között nincs névtelen, 128 TB-os meghajtó; a rendszerpartíció neve „Sloth OS”
- [ ] **Napló mentése** (Rendszer egészség): az elején látszik a futó image és a lemezek
- [ ] **Rendszerinformáció:** „Sloth OS 1.0 (Fedora Atomic 44)”
- [ ] **Nyitott kérdések a 2026-10-19-i ISO tesztjéhez** (a válaszok ide; ami jó, kipipálni). Eddig jó: ujjlenyomat,
  PIN-kód, a titkosított lemez lakatos jelszókérője (a pöttyök javítva):
  - [ ] Tömörített memória-tartalék (Haladó beállítások): átállítás után, újraindítás után kiírja-e az új méretet?
    (még nincs tesztelve)
  - [x] PIN-kód a zárolási képernyőn (Win+L) is működik, nem csak bejelentkezéskor? Igen, mindenhol
  - [x] Rendszerinformáció: „Sloth OS 1.0 (Fedora Atomic 44)” látszik? A „Sloth OS 44” a Sloth Központ Frissítések
    oldalán volt („Jelenlegi verzió”): az rpm-ostree verziócímkéjéből („44.2026…”) készült. Javítva: a rendszerverzió
    saját os-release-éből (PRETTY_NAME); a még le nem töltött frissítésnél „Sloth OS” + dátum
  - [x] Üdvözlő, több app egyszerre: sorban, egyesével települnek? Igen; a Vivaldi is feltelepült. A végén az
    Újraindítás gomb működik
  - [x] Rendszerfrissítés: volt már? A Frissítések oldalon minden rendben volt? Igen, rendben
  - [ ] Battle.net újra, a háttér-előkészítés után: előjön-e a saját telepítője (lásd lent a hibáknál); a
    bootloop miatt (lent) még nem jutott el idáig
- [ ] A reggeli teszt maradéka: titkosítás, frissítés aláírás-ellenőrzéssel, NVIDIA-s gép, Windows mellé (tesztelő kell)
- [ ] A még nyitott hibák figyelése: némítás (melyik gomb: billentyű / tálca ikon; mikor áll vissza: magától, egy
  értesítés hangjára, hangerő-állításra, bejelentkezéskor?), Discover-frissítés a friss appokra (mit frissített:
  magát az appot vagy egy kiegészítőt, pl. `GL.default`?), Vivaldi az Üdvözlőből (a hibaüzenet a mentett naplóban)

### Elkészült 2026-10-15 délután és éjjel (részletek a fázisoknál)
Minden pusholva; a nagy részük csak szimulációval és loop eszközön van kipróbálva, **valódi gépen / VM-ben még nem**.
- **Az első valódi gépes teszt hibái javítva:** élő rendszer nyelve a „Kipróbálom” után, az Üdvözlő állapotszövegei,
  ikonok telepítés után, Battle.net (lásd lent, „Korábban (2026-10-15)”)
- **Önjavító futtató a Windows-programokhoz** (2. fázis): felismerés (umu adatbázis, Steam AppID), receptek (Battle.net,
  Ubisoft Connect, Epic, GOG Galaxy), diagnózis a háttérnaplóból (hiányzó DLL → összetevő, Vulkan-hiba → WineD3D…),
  öngyógyítás más beállításokkal és Proton-verziókkal (Btrfs-pillanatképpel), visszaállás Proton-frissítés után
- **Közös tudás** (2. fázis): Cloudflare Worker + D1 (`sloth-os-knowledge.slothos.workers.dev`), nyilvános
  `bathorizsolt/sloth-os-knowledge` repó (óránkénti export, havi ProtonDB-alap: 287 játék, napi figyelés);
  megosztás csak engedéllyel (új lépés az Üdvözlőben, kapcsoló a Sloth Központban); leírás a README-ben
- **Telepítő** (4. fázis): Windows mellé telepítés (zsugorítás vagy szabad hely, BitLocker / gyors indítás / BIOS
  felismerése, látható boot menü a Windowszal, helyi idős óra), lemeztitkosítás (LUKS2, külön /boot, jelszókérő a
  választott kiosztással és lakat ikonnal)
- **Telepített rendszer:** automatikus NVIDIA-változat (háttérben, értesítéssel, Secure Boot kulccsal), aláírt
  frissítések (mindkét változat aláírása elfogadva, a régebbi telepítések egyszeri átállítása), boot-sorrend
  védelme Windows mellett, értesítések a jobb felső sarokban, `sloth-center --page <oldal>`
- **Fordítások:** minden új szöveg mind az 50 nyelven (Üdvözlő, telepítő, Sloth Központ)

### Reggeli teszt (új ISO a mai CI-build után)
Valódi gépen és/vagy VM-ben; ami nem megy, ide kerüljön vissza hibaként.
- [x] **Élő rendszer:** nyelvválasztás után „Kipróbálom” → a választott nyelven jön fel az asztal; az értesítések jobb felül
- [ ] **Telepítő, teljes lemez:** sima telepítés; utána ugyanez **titkosítással** (indításkor lakat ikon, a jelszó a
  választott kiosztással megy, pl. magyarnál a „z”/„y”; rossz jelszó után újra kéri)
- [ ] **Telepítő, Windows mellé** (VM-ben egy Windowsos lemezzel vagy egy NTFS + EFI-s tesztlemezzel): a felmérés és
  a csúszka, a magyarázatok (pl. hibernált Windows), a telepítés, a boot menüben a Windows-bejegyzés, a Windows
  utána is elindul, az óra jó mindkét rendszerben
- [x] **Első indítás:** csendes boot, rejtett GRUB (Windows mellett látható menü), fiók a telepítőből, Üdvözlő
- [ ] **Üdvözlő:** új „Tapasztalatok megosztása” lépés (igen / nem, a Tovább csak választás után), az appok telepítése
  (mit tölt le / mit telepít, „x / y MB”), az ikonok rögtön látszanak, a Steam a tálcán ikonnal
- [ ] **.exe kezelő:** Battle.net telepítés és indítás a Start menüből (marad-e futva), egy egyszerű .exe, egy játék;
  a háttérnapló (2026-10-19 óta `~/.cache/sloth-os/apps/<program>/naplo/`) és a megjegyzett beállítás
  (`~/Applications/<program>/.sloth/app.json`)
- [x] **Sloth Központ:** Windows-programok oldal (megosztás kapcsoló), Driverek oldal, a többi oldal átnézése
- [ ] **Frissítések:** egy rendszerfrissítés lemegy-e az aláírás-ellenőrzéssel (`rpm-ostree status`: `ostree-image-signed`);
  a tesztlaptopon a régi telepítés átáll-e magától (`sloth-signed-updates`)
- [ ] **NVIDIA-s gépen** (ha van kéznél): magától letölti az NVIDIA-s változatot, értesít, újraindítás után az fut
- [x] Hol látszik még a „Fedora” vagy a „Universal Blue” név (bejelentkező képernyő, Discover, Rendszerbeállítások)

### A reggeli teszt eredménye (2026-10-16, valódi gép, pendrive, teljes lemez, titkosítás nélkül)
Rendben volt: élő rendszer és nyelv, sima telepítés, csendes boot, rejtett GRUB, bejelentkezés, Sloth Központ.
Hátravan: titkosítás, Windows mellé (ehhez tesztelő kell, nincs Windowsos gép), NVIDIA-s gép.
Talált hibák (egyesével javítjuk):
- [x] **Üdvözlő, appok telepítése (nagy hiba):** a folyamat összevissza írja ki az appokat. Ugyanaz az app (pl.
  a Steam) többször is megjelenik, néha ugyanazzal a mérettel, és nem tudni, hogy csak a kijelzés rossz, vagy
  tényleg többször tölti le. Kérés: fentről lefelé, egyesével menjen a telepítés. A letöltés mehet párhuzamosan,
  de a szöveg csak azt írja, hogy „… telepítése”, a letöltést ne említse. Javítva (szimulációval kipróbálva,
  valódi gépen még tesztelni): az ok az egy közös tranzakció volt (minden kiegészítő az app nevével jelent meg);
  most appónként külön tranzakció, előtte méretfelmérés, a felirat „X telepítése…”, alatta „330 MB / 430 MB”
- [x] **Üdvözlő vége:** legyen újraindítás gomb, hogy minden rendesen betöltődjön. Kész (valódi gépen tesztelni):
  ha települt app, az Újraindítás a fő gomb egy rövid magyarázattal; az „Indulhat a móka!” is megmaradt
- [x] Az Üdvözlő bezárása után a tálcán még az alap ikonok látszanak az appok ikonjai helyett (újraindítás után jó).
  Javítva (valódi gépen tesztelni): a tálcára kitűzés előtt `kbuildsycoca6` és ikon-újratöltés jelzés
  (`/KIconLoader iconChanged`); ha ez sem elég, az Újraindítás gomb megoldja
- [x] **.exe kezelő (nagy hiba):** ugyanazt a programot kétszer (vagy többször) is engedi telepíteni, és a Start
  menüben is többször jelenik meg. Javítva (valódi gépen még tesztelni): ha a program már megvan (ugyanaz a név
  vagy ugyanaz a telepítőfájl), „X már telepítve van.”, Megnyitás (alapból) vagy Újratelepítés ugyanabba a
  mappába; új mappa (`-2`, `-3`) és új Start menü bejegyzés nem keletkezik. A régi duplák maradnak, kézzel törölhetők
- [x] A Battle.net továbbra sem indul el, ugyanúgy viselkedik, mint korábban. A közös tudásba nem érkezett adat
  (a `sloth-os-knowledge` repóban 2026-10-16 reggelig nincs export), megnézni, küld-e jelentést a rendszer.
  Valószínű ok megvan, javítva (valódi gépen tesztelni): a Proton `waitforexitandrun` módja az előző
  munkamenetet várja meg indítás előtt, a gyerekfolyamatokat nem, és az umu is csak az elindított folyamatot
  várja. A „Battle.net Launcher.exe” elindítja a klienst, és kilép, ekkor a futtató leáll, és a kliens ablaka
  is eltűnik (Steamből azért ment, mert a Steam minden folyamatot megvár). Most a kliens (`Battle.net.exe`)
  indul közvetlenül (`quirks.launch_target`, mint a Lutris Blizzard-receptjei); az önjavítás adatai a
  klienshez tartoznak, így a régi, téves „nem működik” bejegyzések nem számítanak
- [x] .exe kezelő: ha egy program már fut, és a felhasználó újra elindítja, az új indítás a `waitforexitandrun`
  miatt az előző munkamenet végéig vár („Indítás…”). Javítva (2026-10-19, valódi gépen tesztelni): ha ugyanaz a
  program fut, „X már fut”; ha a környezetében más fut, ahhoz csatlakozik (`runinprefix`)
- [ ] Megnézni, a többi indító (EA app, Ubisoft Connect, Epic, GOG Galaxy) is átadja-e a helyét egy másik
  folyamatnak; ha igen, `quirks.LAUNCHER_STUBS`. Az Epicnél kész (2026-10-19: a 32 bites indító helyett a 64 bites
  kliens, mint a Lutrisban); az EA app (`EALauncher.exe`) és a Ubisoft Connect (`UbisoftConnect.exe`) a Lutrisban
  is az indítóval megy, ezeknél a teszt dönt
- [x] A Steam (Flatpak) nem nyílt meg: kb. 10 mp-ig töltött, utána semmi. Később mégis elindult, épp akkor, amikor
  a Sloth Központban a Battle.net helyett a „Battle net” bejegyzést adta hozzá a Start menühöz (lehet, hogy
  véletlen egybeesés, de nagyon sokat kellett várni rá). Valószínű ok: első indításkor a Steam ablak nélkül letölti
  a saját kliensét. Most a Plasma értesítésben szól erről („A Steam első indítása”, „x MB letöltve”), ha a Steam
  15 mp alatt nem nyílik meg, és az értesítés eltűnik, amikor a Steam ablaka megjelenik
  (`sloth_center/steam_first_run.py`, `sloth-steam-first-run.path`). Valódi gépen tesztelni, és megnézni a
  `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/logs/bootstrap_log.txt`-t, hogy tényleg ez volt-e az ok
- [ ] Titkosított lemezzel telepítve a gép fél óráig a logón állt (2026-10-19-i jelentés). Az image initramfs-e
  rendben (crypt, systemd-cryptsetup, a Plymouth jelszókérő, lock.png, kiosztások); a logón való végtelen várakozás
  a jelszókérésre utal (a systemd a jelszóra időkorlát nélkül vár), a kis lakat valószínűleg nem tűnt fel vagy nem
  látszott. Javítva: nagyobb lakat és beviteli vonal. A következő teszten: látszik-e, és az Esc mit mutat
- [x] A titkosított lemez jelszókérőjén a beírt karakterek helyén négyzetek (az initramfs betűtípusában nincs „●”).
  Javítva (2026-10-19): a pöttyök képből (dot.png), nem szövegből
- [ ] Battle.net telepítése friss (titkosított) telepítés után: 20 percig „Battle.net telepítésének előkészítése…”, a
  Battle.net saját telepítője nem jött elő (2026-10-19-i teszt). Valószínű ok: a bejelentkezés után 3 perccel induló
  háttér-előkészítés (`sloth-windows-prepare`, a Proton és a futtatókörnyezet letöltése) „idle” lemezprioritással
  futott, ami más lemezmunka (appok telepítése, titkosítás) mellett szinte megáll, és az umu csendben megvárta.
  Javítva: az .exe kezelő indításkor átveszi (leállítja a háttérben futót, és az előtérben, látható haladással
  folytatja), a háttérben „best-effort” 7-es prioritás; 60 mp csend után „Még dolgozik…” szöveg. A következő teszten
  figyelni; ha megint így van: Napló mentése (benne a `sloth-windows-prepare` naplója is)
- [ ] **Indítás titkosított lemezzel: a jelszó után a gép újraindul** (2026-10-19 este, a délutáni ISO-ról
  telepített gépen, nem az első indításnál). A lakatos jelszókérő megjelenik, a jelszó beírása után újra a gép
  (BIOS) logója jön, majd megint a jelszókérő. A felhasználó újratelepíti. Kérdések: a GRUB menüben (indításkor
  Esc) az előző bejegyzéssel elindul-e; volt-e előtte rendszerfrissítés vagy NVIDIA-váltás (újraindítás után
  érvényes változás); megjelenik-e magától a GRUB menü a sikertelen indítás után. A felhasználó szerint előtte
  volt egy „újraindítás / bejelentkezés után érvényes” változás, nem emlékszik, melyik; a Haladó beállításokban
  nem állított semmit. Újratelepítés friss ISO-ról.
  VM-teszt (2026-10-19 este, a 20:30-as ISO, magyar kiosztás, titkosítás): telepítés, első indítás (lakat, pöttyök,
  bejelentkező képernyő), Üdvözlőben automatikus bejelentkezés, Újraindítás, jelszó: egyből az asztal. Bootloop
  nem jött elő; a VM-ben nincs NVIDIA és nem volt rendszerfrissítés, a valódi gépen ezeket figyelni
- [x] **Telepítő: a végén fekete képernyő az „Újraindítás” oldal helyett** (VM-teszt 2026-10-19). A telepítés
  lement, de a munkapartíció törlésekor (`finish_partitions`) a systemd leállította a `var-tmp.mount`-ot, vele a
  `basic.target`-et (RequiresMountsFor=/var/tmp) és az élő asztalt, a telepítővel együtt. Ok: a munkapartíció bind
  mounttal volt a /var/tmp fölött, így a var-tmp.mount a partícióhoz kötődött. Javítva: overlayként csatoljuk
  (a systemd szerint a forrás „overlay”, nem a partíció; VM-ben kipróbálva), új ISO kell hozzá. A 20:30-as ISO-val
  is jó a telepítés: ha 90% után elsötétül a kép, 2 perc várakozás után a bekapcsológombbal újra lehet indítani
- [ ] Telepítő, fiók oldal: a jelszómezők helykitöltője angol („Password”)
- [x] **.exe kezelő: egyetlen Windows-program telepítése sem indult** (2026-10-19 este, valódi gép, nem titkosított
  telepítés): a „Still working…” fél óráig forgott. A napló szerint a Proton és a futtatókörnyezet 1 perc alatt
  lejött; a telepítés indításakor `AttributeError: 'App' object has no attribute 'slug'` (runner.py, a délelőtti
  alkalmazáskönyvtár-átalakítás maradéka, a `program.slug` helyett `program.id`). Javítva, és a futtató indításának
  bármilyen váratlan hibája most hibaoldalt mutat, nem forog tovább. Füstpróba Qt-vel kipróbálva
- [x] .exe kezelő: egy félbemaradt telepítés (a telepítő nem futott le, csak a mappa és a recept beállítása jött
  létre) „már telepítve” volt, az Open nem indított semmit. Most csak a kész telepítés számít (Start menü bejegyzés
  vagy a felismerés adata); a félbemaradt mappába az új telepítés kerül, nem duplázódik
- [ ] A Sloth Központ „Napló mentése” fájlneve magyar (`sloth-os-naplo.txt`), angol rendszeren is
- [ ] `tools/tests/test_apps.py`: 4 teszt elbukik ezen a gépen (a 2026-10-19-i javítás előtt is), megnézni
- [x] **Proton és Steam Runtime gyárilag az image-ben** (2026-10-19, a felhasználó kérése): UMU-Proton-10.0-4 és
  a Steam Linux Runtime (sniper 3.0.20261007.263965) rögzítve, ellenőrzőösszeggel (`files/scripts/windows-runtime.sh`,
  `/usr/share/sloth-os/windows-runtime`, 2,2 GB kicsomagolva). Első használatkor a `windows-runtime-seed` a
  felhasználó mappájába másolja (az .exe kezelő „Első indítás előkészítése…” lépése és a sloth-windows-prepare),
  utána az umu internet nélkül is indul, és a háttérben frissít. Helyben kipróbálva (bemásolás, pv-verify: OK);
  valódi gépen tesztelni: friss telepítés, internet nélkül egy .exe. Az ISO mérete: a végén az összevonással
  (`SLOTH_SQUASH=1`) és ha kell, máshogy csökkenteni
  - [ ] Később: gyári sablon-környezet a leggyakoribb összetevőkkel (pl. vcrun2022), ha a tesztek szerint kell
- [ ] Üdvözlő internet nélkül: az app-oldalakon a „Kihagyom” nem lép tovább (VM, 2026-10-19)
- [ ] A némítás gomb elnémít, de nem marad úgy: a hangerő visszaáll a korábbira, valami felülírja. 2026-10-19:
  megint előjött; a némítás szinte azonnal feloldódik, amint bármelyik gombot megnyomja (billentyűzet)
- [x] **Dolphin, Eszközök: a névtelen, 128 TB-os meghajtó** (2026-10-19 este, a felhasználó képei és a mentett
  napló alapján): nem loop eszköz (a gépen nincs), hanem maga a rendszer gyökere, a /-re csatolt composefs overlay.
  A KDE Solid az overlay csatolások közül szándékosan mutatja a /-re csatoltat (élő rendszerekhez), és csak az
  /etc/fstab `x-gvfs-hide` opciójával rejthető el (upstream nincs rá javítás). Javítva:
  `sloth-hide-root-overlay.service` pótolja a `composefs / overlay ro,noauto,x-gvfs-hide 0 0` sort (a meglévő
  gépeken is). VM-ben kipróbálva: `StorageAccess.ignored = true`, újraindítás után a systemd-remount-fs rendben.
  A 128 TiB a „Tulajdonságok” rekurzív mérete, benne a /proc/kcore virtuális méretével. Mellette a rendszerpartíció
  „root” néven látszott (a Dolphin a fájlrendszer címkéjét mutatja, az udev-név nem hat): az új telepítő „Sloth OS”
  címkét ad; a korábbi telepítéseken marad a „root”
- [x] **A sikeres indítás jelzése titkosított lemezen nem működött** (VM, 2026-10-19): a `boot-env` a
  /dev/mapper/… gyökér szülőjét (a partíciót) vette lemeznek, „Nincs EFI partíció.”, a sloth-boot-ok.service
  hibás, így minden indításnál előjött volna a boot menü. Javítva: a lemez az ősláncból (`lsblk -s`)
- [x] Dolphin, Eszközök: az SSD mérete 128 TB-nak látszik. Első javítás (2026-10-19, nem elég, lásd fent): a
  névtelen bejegyzés a composefs (a Fedora 42 óta csak olvasható rendszerkép) loop eszköze volt; a 128 TB
  valószínűleg a /proc/kcore virtuális mérete a gyökér méretszámításában. Udev-szabály rejti el
  (`90-sloth-udisks.rules`), a rendszerpartíció neve „Sloth OS”. Ha a teszten mégis látszik: Napló mentése, az
  elején a lemezek és a loop eszközök
- [ ] A Discover az Üdvözlőből épp most telepített appokat (pl. a Steamet) is frissítette (megnézni, miért).
  Valószínű ok (2026-10-19): az alap image automatikus app-frissítője (`flatpak-system-update.timer`, 2 perccel a
  bekapcsolás után) az Üdvözlő alatt futott. Most kimarad, amíg az Üdvözlő fut; a teszten figyelni.
  2026-10-19-i teszt: a felhasználó szerint csak valami Fedora-alapcsomagot frissített (valószínűleg egy
  Flatpak-futtatókörnyezetet, pl. a Fedora Platformot vagy a `GL.default`-ot), az appokat nem; így rendben van
- [x] A rendszer neve „Sloth OS 44” (a Fedora verziószáma látszik): a Sloth OS saját verziószámot kapjon (pl. 1),
  és valahol (pl. a Rendszerinformációban) jelenjen meg, hogy Fedora Atomic alapú. Kész (valódi gépen
  megnézni): „Sloth OS 1.0 (Fedora Atomic 44)” (`branding.sh`: VERSION, PRETTY_NAME; a VERSION_ID marad 44;
  `/etc/xdg/kcm-about-distrorc`: UseOSReleaseVersion)

### Teendők fontossági sorrendben
**Publikálás előtt kötelező:**
1. [ ] **A fenti teszt végig, és a talált hibák javítása.** Sok nagy új funkció van, amit csak szimulációval
   próbáltunk ki; publikálás előtt mindnek valódi gépen kell működnie. A reggeli teszt hibáiból még nyitott
   (sorrendben): némítás (a hangerő visszaáll; a mi kódunk nem nyúl a hangerőhöz, valódi gépen kell megfigyelni),
   Discover-frissítés a friss appokra, a többi indító ellenőrzése (`LAUNCHER_STUBS`). A Dolphin 128 TB és az
   újraindítás futó programnál javítva (2026-10-19), a teszten ellenőrizni
2. [ ] **Régi (BIOS-os) gépek:** elindul-e a pendrive BIOS-módban, telepítés BIOS-os gépre (a teljes lemezes
   telepítésnél a BIOS boot partíció már megvan); Windows mellé BIOS-on maradhat „nem támogatott” magyarázattal
3. [ ] **A repó publikussá tétele** és a napi automatikus build visszakapcsolása (`.github/workflows/build.yml`). Ettől függ:
   a telepített gépek bejelentkezés nélkül kapnak frissítést (most a privát registry miatt nem), és a telepítő
   `--skip-fetch-check` nélkül is ellenőrizheti a frissítések elérhetőségét.
   - [x] Titkok és személyes adatok a repó teljes történetében (2026-10-19): gitleaks (113 commit, minden ág):
     nincs találat; kézi keresés (e-mail, név, gépnév, saját útvonalak, IP-címek, kulcsok): minden commit a GitHub
     noreply címével; a `deploy-vm.sh` (`0fede6b`) csak egy VM-belső címet tartalmaz (`10.0.2.100`); az
     `SB_PASSWORD = "universalblue"` a Universal Blue nyilvános Secure Boot jelszava. A képekben nincs személyes
     metaadat; a `docs/branding/logo-source.png` C2PA-jelölése csak annyit mond, hogy MI-vel készült
4. [ ] **ISO-tárhely és letöltés:** a GitHub kiadásaiba fájlonként legfeljebb 2 GB tölthető fel, az ISO 5,6 GB;
   ingyenes tárhely kell (pl. Cloudflare R2, 10 GB-ig ingyenes) ellenőrzőösszeggel és aláírással
5. [ ] **Weboldal és dokumentáció:** letöltés, pendrive-ra írás (Windowsból is, GUI-val), első lépések, gyakori kérdések
   (Windows mellé telepítés, titkosítás, NVIDIA, adatvédelem). Kész (2026-10-19): a `codex/website-docs` kezdeménye
   átnézve és javítva a `website/` mappában (kezdőlap, első lépések, Windows-programok, adatvédelem, GYIK; a valódi
   logó, licencek és ODbL a láblécben; Pages workflow, a publikus repó után indul). Hátravan: letöltési oldal és
   pendrive-írás útmutató (amikor van letölthető ISO), Windows mellé telepítés, titkosítás, NVIDIA a GYIK-ben
6. [ ] **Licencek és nevek:** kész (2026-10-19): a kód Apache-2.0 (`LICENSE`, mint a Universal Blue és a BlueBuild),
   a saját grafika (logó, háttérképek, boot animáció) CC BY-SA 4.0, az Üdvözlő app-ikonjai a gyártóiké (`NOTICE`;
   az image-ben `/usr/share/licenses/sloth-os/`, a háttérképek adataiban is). Hátravan: a ProtonDB-adatok
   ODbL-megjelölése a letöltési oldalon (a weboldallal együtt).
   - [x] A „Sloth OS” név (2026-10-19, nem jogi vélemény): nincs ilyen nevű operációs rendszer (egy böngészős
     diák-tréfaprojekt van a GitHubon); az USA-ban egy „SLOTH” védjegy a 9. osztályban egy „slow TV” lejátszó appra
     (USPTO 6130782), más termékkör. Az EUIPO gépi keresése nem működött: publikálás előtt kézzel a TMview-ban és
     az SZTNH-nál is megnézni, vagy védjegyjogászt kérdezni
7. [ ] **A fordítások anyanyelvi átnézése** legalább a leggyakoribb nyelveken (angol, német, spanyol, francia…);
   a többi maradhat gépi, jelölve

8. [ ] **Windowsról érkezőknek hiányzó alapok** (2026-10-19, a felhasználóval egyeztetve; a munka méretét még
   egyeztetni):
   - [ ] **Saját fájlok mentése és visszaállítása:** automatikus Btrfs-pillanatképek a home-ról (óránként / naponta,
     a régiek maguktól törlődnek), a Dolphinban jobb klikk → „Korábbi verziók” (mint a Windowsban), a Sloth
     Központban kapcsoló a külső lemezre mentéshez és a visszaállításhoz
   - [ ] **A gép alaphelyzetbe állítása** („Reset this PC”): a fájlok megtartásával vagy mindent törölve; a
     rendszerbeállítások gyári állapotra, frissítés a legújabb verzióra. Sloth Központból, és ha a rendszer nem
     indul, a boot menüből is
   - [ ] **Átköltözés Windowsról:** Windows mellé telepítéskor az Üdvözlő felajánlja a Dokumentumok, Képek, Asztal,
     Zene, Videók mappák és a böngésző-könyvjelzők áthozását

**Fontos, de a publikálást nem akadályozza:**
- [ ] **OneDrive és Google Drive a Dolphinban:** a Google Drive a KDE Online fiókjaival (kio-gdrive), a OneDrive-hoz
  külön kliens kell (megnézni, melyik karbantartott és Flatpakként vagy RPM-ként elérhető); bekapcsolás GUI-ból
- [ ] **Telefon összekötése** (a Windows „Phone Link” megfelelője): a KDE Connect a karcsúsításnál kikerült;
  az Üdvözlőben legyen választható (Flatpak), és a tűzfalban a portjai nyíljanak meg hozzá
- [ ] **BIOS/firmware frissítés** (fwupd, LVFS; a HP is támogatja): megnézni, hogy a Discover mutatja-e; ha nem, a
  Sloth Központ Frissítések oldalára
- [ ] **Nyomtató és szkenner:** megnézni, benne van-e a `hplip` (HP) és egy szkennelő app (pl. Skanpage) az
  image-ben; teszt egy HP nyomtatóval
- [ ] **Gyerekfiók és szülői felügyelet:** képernyőidő, mit telepíthet, mely appokat indíthatja; a Sloth Központ
  Fiók és biztonság oldalán
- [ ] **Minden app frissítése egy helyen, a Discoverben** (döntés: 2026-10-16). A Discover már most minden Flatpakot
  frissít, amit az Üdvözlő a Flathubról telepít (ezért frissítette rögtön a Steamet is). Hátravan:
  - [ ] **Saját Flatpak-tároló a GitHub-csomagos appoknak** (pl. ArtCraft; ez az első lépés): egy GitHub Action a
    kiadásokból (SHA256 ellenőrzéssel) feltölti őket egy saját, aláírt Flatpak-tárolóba (pl. Cloudflare R2, ugyanott,
    ahol az ISO lesz). Az Üdvözlő innen telepít, a Discover innen frissít, a `sloth-github-bundle-update.timer`
    elhagyható (a már telepítettek egyszeri átállítása a tárolóra). Kell hozzá: R2-tároló és GPG-kulcs a CI-ban
  - [ ] **Windows-programok a Discoverben:** saját Discover-bővítmény (C++, KDE-modul), amely a telepített
    Windows-programokat és a Proton-frissítést mutatja. Nagy munka, és minden Plasma-frissítésnél karban kell
    tartani; a programok (Battle.net, Steam, Epic…) amúgy is maguktól frissülnek. Előbb megnézni, hogy egy
    egyszerűbb út (pl. AppStream-adat + a Sloth Központ Frissítések oldala) nem elég-e
  - [x] **Rendszerfrissítés a Discoverben** (2026-10-19): kiderült a forrásból, hogy nincs dupla frissítés. A
    Universal Blue a KDE-s image-ből kiveszi a Discover rpm-ostree-bővítményét (`plasma-discover-rpm-ostree`), így a
    Discover csak az appokat mutatja; a rendszert a Sloth Központ frissíti. Közben a `ublue-os-update-services` a
    rendszerfrissítést magától előkészíti (`AutomaticUpdatePolicy=stage`), az appokat (Flatpak) pedig bekapcsolás után
    2 perccel és naponta magától frissíti (nem mért kapcsolaton). Kész: a Frissítések oldalon „Appok” rész (mi frissül
    magától, „Megnyitás a Discoverben”); az app-frissítő nem fut, amíg az Üdvözlő fut (drop-in a
    `flatpak-system-update` / `flatpak-user-update` szolgáltatásokhoz)
- [x] Windows mellett: a boot-sorrend teljes védelme (2026-10-19; valódi Windowszal még tesztelni): Windows-oldali
  segéd (`/usr/share/sloth-os/windows-helper/`: `Sloth-OS-boot.cmd` + `sloth-boot-order.ps1`, szövegek 50 nyelven).
  Egyszer kell elindítani a Windowsban (dupla kattintás, UAC): ütemezett feladat minden Windows-induláskor és naponta,
  rendszerjogokkal; ha a Windows Boot Manager került előre, visszateszi a Sloth OS-t (`bcdedit /set {fwbootmgr}
  displayorder … /addfirst`), más sorrendet (pl. pendrive) békén hagy. A bcdedit nyelvfüggő kimenetéből csak a
  GUID-okat és a „Sloth OS” nevet olvassa (hamis, magyar nyelvű kimenettel kipróbálva). A telepítő Windows mellé
  telepítéskor a Windows Nyilvános asztalára teszi („Sloth OS” mappa), utólag a Sloth Központ → Haladó beállítások
  → „Segéd elhelyezése a Windowsban” (hibernált / gyors indítással leállított Windowsnál érthető üzenet)
- [ ] Külön NVIDIA-s ISO „haladóknak” (internet nélkül is NVIDIA-illesztővel indul), ha a tárhely engedi
- [x] Linuxos csomagok kezelője (.AppImage, .deb, .rpm; Mac-fájloknál érthető üzenet) – 2. fázis (2026-10-19,
  valódi gépen még tesztelni; részletek a 2. fázisnál)
- [x] .exe kezelő: „javítás / újratelepítés” – 2. fázis (2026-10-19: Sloth Központ → Windows-programok → Javítás,
  Újratelepítés)
- [ ] **Alkalmazáskezelés, következő lépések** (a 2026-10-19-i alapra):
  - [x] Import más helyekről (2026-10-19, valódi Lutrisszal / Bottlesszel még tesztelni): a Steam-átvétel
    általánosítva (`sloth_common/apps/imports.py`): Steam (`shortcuts.vdf`), Lutris (`pga.db` + `games/*.yml`, natív
    és Flatpak), Bottles (`bottle.yml`, External_Programs), korábbi `~/.wine` (registry + parancsikonok). „Az eredeti
    programmal” (a Steam / Lutris / Bottles indítja) vagy „Átvétel” (reflink-másolat); az eredetihez nem nyúl
  - [x] Receptek a közös tudásból (2026-10-19): `recipes.json` a `sloth-os-knowledge` repóban (kézzel szerkesztve,
    a `recipes` Action minden változásnál és PR-nál ellenőrzi: `seed/validate_recipes.py`), és beépítve az image-ben
    (`/usr/share/sloth-os/recipes.json`, internet nélkül is); a `sloth-windows-prepare` letölti, az újabb (`updated`)
    nyer. A gép is újra ellenőrzi (`sloth_common/apps/recipes.py`): csak engedélyezett mezők és értékek (indító →
    kliens, a Start menübe kerülő és a kihagyandó .exe-k, összetevők, Proton-kapcsolók, paraméterek, DLL-kikapcsolás
    `=d`/`=b`; parancs, tetszőleges változó vagy natív DLL nem). A kódba írt receptek adatai átkerültek; a kódban csak
    a beállításfájlok írása maradt (Battle.net, Ubisoft). Első receptek: Battle.net, Epic, GOG Galaxy, Ubisoft Connect
  - [x] A Linuxos csomagok kezelője (lent) is a `~/Applications`-be telepítsen (AppImage), ugyanazzal a könyvtárral
    (2026-10-19: `sloth_common/apps/packages.py` `install_appimage`, a háttérben frissül)
- [ ] A Steames játékok bevonása az önjavításba és a közös tudásba
- [ ] Bejelentkezés, következő lépések (lásd a 3. fázisban, Fiók és biztonság):
  - [ ] A PIN-kód tárolása a TPM-ben (most scrypt-hash a `/etc/sloth-os/pin` alatt; a TPM a próbálkozásokat
    hardveresen is korlátozná, és a hash nem vihető át másik gépre)
  - [ ] Céges fiók: Entra ID (a mostani Active Directory mellé)
  - [ ] A jelszótároló (KWallet) nyitása jelszó nélküli belépésnél (PIN, ujjlenyomat, biztonsági kulcs): most
    az első használatkor kéri a jelszót
- [x] Fejlesztői pult a Sloth Központban (repó, build, tesztelés GUI-ból) – 3. fázis (2026-10-19, lásd lent)
- [ ] Haladó beállítások folyamatos bővítése – 3. fázis. 2026-10-19: tömörített memória-tartalék (zram: alap /
  nagyobb / ki, `sloth-helper zram`, a `/etc/systemd/zram-generator.conf`; Fedora 44-ben a zram-generatorral
  ellenőrizve), PIN-kódos bejelentkezés (Fiók és biztonság)
- [x] ISO-méret: a rétegek összevonása, helytakarékos ISO-build – 4. fázis (2026-10-19, lásd a 4. fázisnál)
- [ ] A Vivaldi nem települt fel az Üdvözlőből (oka ismeretlen; a teszten figyelni). Lehetséges ok: a fenti
  automatikus app-frissítő egyszerre futott az Üdvözlővel (most kimarad, amíg az Üdvözlő fut)

## Korábban (2026-10-15)
- Első teszt valódi gépen (2026-10-15 délután, pendrive-ról, Intel UHD-s tesztlaptop). A talált hibák javítva,
  a következő image-en és ISO-n újra megnézni:
  - [x] Az élő rendszerben a „Kipróbálom” után angol maradt az asztal: most a választott nyelven indul újra
    a Plasma (`plasma-localerc` + a munkamenet környezete + a plasmashell újraindítása)
  - [x] Az Üdvözlő telepítés közben csak a letöltött MB-ot írta: most azt is, melyik app (vagy melyik app
    összetevője) töltődik / települ, letöltéskor „x / y MB”; a folyamatjelző a méret szerint halad
  - [x] A frissen telepített appoknak (a tálcára tett Steamnek is) újraindításig nem volt ikonja: a Flatpak
    ikonmappája nem létezett a Plasma indulásakor (nincs előtelepített app). Most `tmpfiles.d` hozza létre
  - [x] A Battle.net telepítés után elindult, majd kb. 10 mp múlva kilépett (Steamen keresztül működött): az
    .exe kezelő most a Lutris receptje szerint indítja (hardveres gyorsítás ki a Battle.net.config-ban,
    `locationapi=d`), `sloth_exe/quirks.py`; ide jöhetnek a többi indító (EA, Ubisoft, Epic) beállításai
  - A Vivaldi nem települt fel az Üdvözlőből (a teendők között, lásd fent)
- Teendők 2026-10-15-re: új ISO és teljes VM-teszt (fiók a telepítőben, KDE-varázsló nélküli első indulás, rejtett
  GRUB és csendes boot, Üdvözlő, asztal, Sloth Központ, .exe kezelő); a gaming-pontok átnézése; Fejlesztői pult.
- Minden fordítás kész (Üdvözlő, telepítő, .exe kezelő, Sloth Központ: 50 nyelv); anyanyelvi átnézés hátravan.
- Negyedik VM-teszt (2026-10-15, Hyper-V): a délelőtti ISO (6,9 GB) telepítése a `bootc` után elakadt; az ok
  megvan és javítva (4. fázis). Ugyanaznap elkészült még: a start menü nevei mind az 50 nyelven, karcsúbb image
  (a hibaelhárító eszközök maradnak), Falkon a Firefox helyett az élő rendszerben, gyorsabb ISO-build
  podman commit nélkül, nem kapcsol le a képernyő telepítés közben.
- Következik: a CI buildelje újra az image-et, utána új ISO (lehetőleg az erősebb gépen; a build kb. 45 GB helyet
  kér), majd teljes VM-teszt. A VM-ben a dinamikus memória legyen kikapcsolva.

## Korábban (2026-10-14 este)
- Harmadik VM-teszt (új ISO, 4 GB RAM, internet nélkül): a saját telepítő végigment. Működik: nyelvváltás,
  élő billentyűzetváltás a próbamezőben, lemeznév (`vda · HDD · 43 GB`), fókuszkeret, haladó folyamatjelző,
  újrapróbálás hiba után, munkapartíció (rendszerszinten a `/var/tmp` fölé csatolva, utána a rendszerpartíció
  39,5 GB-ra nőtt), boot-bejegyzés átnevezése, nyelv/billentyűzet beírása, Firefox átmásolása internet nélkül;
  a KDE üdvözlője nem jön elő. Az első indulás magyarul hozza a Plasma Setupot.
  Ott álltunk meg: Plasma Setup, fiók létrehozása (teszt / sloth). Következik: Sloth Üdvözlő (új „Jelszavak”
  lépés), asztal, Sloth Központ új oldalai, .exe kezelő.
  Új teendők a tesztből:
  - [x] A KDE első indítási varázslója (Plasma Setup) kikerült: a fiókot a Sloth OS telepítője kérdezi meg
    (új „Fiókod” lap), első induláskor a `sloth-first-user` szolgáltatás hozza létre; a többit az Üdvözlő
    kérdezi. VM-ben még tesztelni (új image + új ISO kell)
  - [x] Az új ISO-ba már a javított telepítő-segéd kell (a VM-ben kézzel volt átmásolva): új ISO építése (2026-10-15)
- Második VM-teszt (első saját ISO, 6,8 GB): rejtett GRUB, szöveg nélküli boot, Firefox a tálcán, nyelvváltás
  a választón azonnal: rendben. A telepítés nem ment végig; a talált hibák javítva (4. fázis, „Saját telepítő”),
  de VM-ben még újra kell nézni. Következő lépés: új ISO (`tools/build-iso.sh` Linuxon, `tools/build-iso.ps1`
  Windowson; kell a GitHub CLI `read:packages` joga), majd VM-teszt végig: telepítés, első indítás, Üdvözlő.
- A Sloth Központ 3. fázisbeli nyitott pontjai elkészültek (felhasználói szolgáltatások, környezeti változók,
  verziók listája, kontrollerek, jelszó nélküli rendszergazda, bejelentkezési módok, Játékok modul); VM-ben még tesztelni.
- A Sloth Központ fordítása kész mind az 50 nyelvre (2026-10-15); az anyanyelvi átnézés még hátravan.
- Utána: a Windows mellé telepítés.

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
  - [x] Appok telepítése a varázslóból (2026-10-15, valódi gépen: működik; a Vivaldi nem települt fel)
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
- [x] Boot menü elrejtése (csak hibás indítás után jelenik meg) és csendes boot: a bootupd GRUB-sablonja minden indításkor 1 mp-re kirakta a menüt, és a `menu_auto_hide`-ot nem nézi, ezért saját `custom.cfg` (`/usr/lib/sloth-os/grub-custom.cfg`, állapot az EFI partíción, `sloth-boot-ok.service`); a bootc-s telepítésből hiányzó `quiet rhgb splash` a kargs közé került (VM-ben még tesztelni)
- [x] Háttérképek: 16 kép 4K-ban (MI-felskálázással), az ultraszélesek 5120×2160-ban is; alapértelmezett: „Metallic Sloth Over Silver Waves” (asztal és zárolási képernyő)
- [x] Windows-szerű alapértelmezett Plasma-elrendezés: tálca alul, start menü a logóval, rögzített appok; bejelentkezés utáni betöltőképernyő a boot animációval (`files/system/usr/share/plasma/look-and-feel/org.slothos.desktop/`; VM-ben még tesztelni)
- [x] Más elrendezések választhatóan az üdvözlő varázslóban: Windows 10, Windows 11 (középre igazított), macOS-szerű (felső sáv + lebegő dokk); VM-ben még tesztelni
- [x] Színtémák: Silver sötét (alapértelmezett) és világos, Hófehér, Éjfekete, Ködkék, Éjkék, Zsálya (`tools/branding/gen_colors.py`, előnézet: `docs/branding/color-schemes-preview.png`)
- [x] Saját Plasma téma: a stílus kész, mást nem tervezünk (döntés: 2026-10-15)
- [x] Bejelentkező képernyő (Plasma Login Manager, tartalékként SDDM): Sloth OS háttérkép, Sloth Silver színek; VM-ben még tesztelni
- [ ] Ellenőrizni, hol látszik még "Fedora" vagy "Universal Blue" név. Eddig:
  - [x] Rendszerinformáció, boot menü bejegyzések, gépnév: az os-release-ből jönnek (Sloth OS)
  - [x] A KDE üdvözlő appja (`plasma-welcome`) kikerül az image-ből (`files/scripts/remove-default-apps.sh`), a Sloth
    Üdvözlő fut helyette. A korábbi `kded6rc`-s kikapcsolás nem működött (az élő rendszerben eltakarta a telepítőt)
  - [x] Alapértelmezett háttérkép: a saját Sloth OS háttérkép
  - [x] Firmware (BIOS/UEFI) boot-bejegyzés neve: a saját telepítő „Sloth OS”-re nevezi át (egy `lsblk`-hiba miatt
    eddig nem futott le, javítva; VM-ben még tesztelni)
  - [ ] VM-ben végignézni: bejelentkező képernyő, Discover, Rendszerbeállítások
  - [x] A Sloth eszközök neve és leírása a start menüben mind az 50 nyelven (2026-10-15; eddig minden nyelven
    magyarul látszott). A `.desktop` fájlokat a `tools/gen_desktop_entries.py` írja a fordításokból

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
  - [x] Javítás és újratelepítés a Sloth Központban (2026-10-19)
  - [x] Játékonkénti javítások automatikusan (umu adatbázis: GAMEID a program neve alapján) – lásd lent
- [ ] **Önjavító futtató: minden Windows-program elinduljon, beállítás nélkül** (ötlet: 2026-10-15). Egy mindenre
  jó Proton-beállítás nincs (ami az egyiknek kell, a másikat elrontja), ezért a rendszer programonként maga
  találja meg a működőt. A felhasználó ebből csak annyit lát: „Indítás…”, és a program elindul. Lépések:
  1. [x] **Felismerés** (`sloth_exe/identify.py`): a .exe verzióadataiból (termék neve; a „Launcher”,
     „Setup”, verziószám levágva) az umu adatbázisa (a rendszerrel jön, a `sloth-windows-prepare` frissíti),
     ha ott nincs, a Steam áruháza (pontos névegyezés) → `GAMEID=umu-<Steam AppID>`. Így jönnek az
     umu-protonfixes javításai és a Proton saját, AppID-hez kötött javításai. Egyszer keres, az eredményt megjegyzi
  2. [x] **Receptek** az ismert indítókra (`sloth_exe/quirks.py`, a Lutris kipróbált telepítői alapján, a
     Protonhoz igazítva): Battle.net (GPU-gyorsítás ki, `locationapi=d`), Ubisoft Connect (overlay ki,
     d3dcompiler_43), Epic (`-opengl -SkipBuildPatchPrereq`), GOG Galaxy (`libglesv2=d`, Visual C++, .NET 4.8,
     `/runWithoutUpdating /deelevated`). Az EA app és a Rockstar Lutris-receptje csak betűtípusokat tesz fel, azokat
     a Proton hozza. Valódi indítókkal még tesztelni
  3. [x] **Diagnózis** (`sloth_exe/diagnose.py`): a futtató kimenete mindig a háttérben megy
     (`<program>/naplo/<exe>.log`, a „fixme” zaj nélkül). Ha a program gyorsan kilép, a felismert hibák javítása:
     hiányzó DLL → a megfelelő összetevő (Visual C++ 2005–2022, DirectX-részek, XAudio, PhysX, MSXML, VB6…,
     winetricks az umu-n keresztül); .NET → dotnet48; Vulkan/DXVK-hiba → WineD3D; beépített böngésző
     GPU-hiba → `--disable-gpu`
  4. [x] **Öngyógyítás** (`sloth_exe/heal.py`): ha nincs felismert ok, próbálkozási sor (alap, fsync nélkül,
     WineD3D, GE-Proton, egy régebbi Proton; indításonként legfeljebb 4 próba, utána érthető hibaüzenet).
     Proton-váltás előtt reflink pillanatkép a program mappájáról (Btrfs; más fájlrendszeren a Proton-váltás
     kimarad, csak előre léphet), sikertelen próba után visszaáll. A bevált beállítást .exe-nként megjegyzi.
     Ha egy indító átadja a helyét (pl. Battle.net Launcher → Battle.net), az nem hiba: megvárja
  5. [x] **Visszaállás frissítés után:** a bevált verzió után előbb az újabbal próbál; ha az nem megy, vissza a
     bevált verzióhoz (pillanatképből), és annál a programnál az marad, amíg nem jön egy még újabb.
     A régi Protonokat a `sloth-exe --maintenance` törli (a legújabb, egy tartalék és a programok által
     használt verziók maradnak)
  6. [x] **Közös tudás** (`sloth_exe/community.py`, szolgáltatás: `services/knowledge/`): ami más Sloth OS-es
     gépeken bevált, az nálunk az első próba. Olvasás: statikus `knowledge.json` a nyilvános
     `bathorizsolt/sloth-os-knowledge` repóból (a `sloth-windows-prepare` tölti le). Megosztás: csak ha a
     felhasználó bekapcsolja (Sloth Központ → Windows-programok → „Tapasztalatok megosztása”, alapból ki);
     a jelentés névtelen (a program nevéből csak hash, a gép egy véletlen szám), sorba kerül, és a háttérben
     megy el. A szolgáltatás Cloudflare Worker + D1 (`https://sloth-os-knowledge.slothos.workers.dev`):
     csak engedélyezett beállításokat fogad el, gépenként egy szavazat, legalább 3 gépen és 75%-ban
     bevált beállítás kerül közzé, címenként napi 500 jelentés. Az összesítést óránként a knowledge repó
     GitHub Actionje írja ki (havonta életjel, hogy az ütemezés ne álljon le)
     - [x] Az Üdvözlőben külön lépés (a Jelszavak után): mi ez, mi megy el és mi nem; a felhasználó választ
       (igen / nem, egyik sincs előre bejelölve), később a Sloth Központban átállítható. Leírás: README
     - [x] Alap a ProtonDB nyílt adataiból (ODbL): a knowledge repó `protondb` Actionje havonta a legfrissebb
       kiadásból játékonként és GPU-gyártónként kiszedi a működő beállítást (Proton-változat, kapcsolók,
       összetevők; csak az utolsó 2 év, legalább 3 beszámoló, csak ha nem az alapértelmezett). 2026-10: 287
       játék. A felismert (Steam AppID-s) játékoknál ez az első próba, ha nincs saját vagy Sloth OS-es adat
     - [x] Bővített engedélyezett kapcsolók: NVAPI, NVIDIA elrejtése, large address aware, heap delay free,
       D3D10/11 ki, régi GL-szöveg, write watch ki (a Workerben, a gépen és a ProtonDB-feldolgozóban is)
     - [x] A szolgáltatás figyelése (2026-10-16): a knowledge repó `monitor` Actionje naponta ellenőrzi a Workert, a
       jelentések ellenőrzését és az exportot; hiba esetén issue nyílik (e-mail), ha újra rendben van, lezárul.
       A hibaág még nincs élesben kipróbálva
  - Kipróbálva (2026-10-15) a valódi vezérlővel és egy hamis futtatóval: hiányzó DLL, Vulkan-hiba, ismeretlen
    összeomlás, frissítés utáni visszaállás Btrfs-en, reménytelen eset, indító-átadás, ottmaradt Wine-folyamatok.
    Valódi gépen még nincs kipróbálva
  - Teszt: a nagy indítók (Battle.net, EA, Ubisoft, Epic, Rockstar, GOG) és pár népszerű játék végigpróbálása
    minden nagyobb változás után, valódi gépen (AMD, NVIDIA, Intel)
- [x] Steamben a Proton alapból bekapcsolva minden játékra (`sloth-steam-proton-default.service`; VM-ben még tesztelni)
- [x] MangoHud / gamescope Flatpak Vulkan rétegek a Steam Flatpakhoz (`sloth-steam-vulkan-layers.timer`; VM-ben még tesztelni)
- [x] Érthető hibaüzenet, ha egy játék anti-cheat miatt nem futhat Linuxon (.exe kezelő: Vanguard, FACEIT, Ricochet… esetén rögtön szól; Easy Anti-Cheat / BattlEye esetén akkor, ha a játék gyorsan kilép). Hátravan: ugyanez a Steames játékoknál
- [x] **Linuxos csomagok kezelője** (2026-10-19, valódi gépen még tesztelni): a .exe kezelő nyitja meg őket (a fájl
  tartalma alapján ismeri fel), közös kód: `sloth_common/apps/packages.py`. AppImage: a `~/Applications/<név>/` alá
  (másolat, Btrfs-en reflinkkel), futtathatóra, a saját nevével, ikonjával és kategóriáival a Start menübe
  (`sloth-exe --run`, áthelyezés után is indul), vagy csak futtatás; a FUSE 2 (`fuse-libs`) bekerült az image-be.
  .deb: Ubuntu-dobozba (`sloth-ubuntu`), .rpm: Fedora-dobozba (`sloth-fedora`), az új appok a Start menübe
  (`distrobox-export`), mellette „Keresés a Discoverben”; eltávolításkor a dobozból is törlődik. Mac-fájlok: érthető
  üzenet és Discover-keresés; Mac-es parancsfájlt nem futtatunk. A Sloth Központ oldala ezért „Programok” lett.
  A saját fájl nélküli programok (máshonnan indítottak, dobozosak) adatai rejtve vannak
  (`~/.local/share/sloth-os/apps/`), hogy ne legyen üres mappa a `~/Applications`-ben. Szintén kész (2026-10-19):
  AppImage-frissítés a háttérben (`sloth-exe --maintenance`, a `sloth-windows-prepare.timer` hívja): az AppImage saját
  frissítési adatából (ELF `.upd_info`: `zsync|…` vagy `gh-releases-zsync|…`) a `.zsync` fejléce, SHA-1 egyezés
  esetén nincs teendő, különben teljes letöltés, ellenőrzés, csere; csak nem mért kapcsolaton, és ha a program nem
  fut. Valódi AppImage-en kipróbálva (AppImageUpdate): az adat kiolvasása és a fejléc. Ha egy .deb, .rpm vagy
  AppImage a Flathubon is megvan (pontos névegyezés), azt ajánljuk („Telepítés a Discoverből” a fő gomb).
  Az eredeti terv: a netről letöltött Linux-appok is
  dupla kattintásra települjenek, folyamatjelzővel, Start menü bejegyzéssel, és a Sloth Központban
  eltávolíthatók legyenek. Most egyiket sem kezeli semmi:
  - `.AppImage`: letöltve nem futtatható, dupla kattintásra a „Megnyitás ezzel…” jön; sokhoz `libfuse2` is kell
    (ellenőrizni, benne van-e az image-ben). Terv: saját mappába, futtathatóra, Start menü, frissítés, ha az
    AppImage támogatja
  - `.deb`: Fedorán egyáltalán nem telepíthető. Terv: a háttérben egy Ubuntu-dobozba (`distrobox`, a Sloth
    Központ dobozkezelése már megvan), az app a Start menüben natívként jelenik meg, a „doboz” szó nem látszik
  - `.rpm`: Atomic rendszeren nem telepíthető „csak úgy”. Terv: ha van Flatpak változata, azt ajánljuk;
    különben Fedora-dobozba; a rendszerbe rétegezés csak a haladó beállításokban
  - `.flatpakref` / `.flatpak`: a Discover már kezeli (VM-ben ellenőrizni)
  - Mac-appok és -lemezképek: `.dmg`, `.xip`, `.pkg`, `.mpkg`, `.app` (zip-ben is: `.app.zip`), `.sparseimage`,
    `.sparsebundle`, `.cdr`, `.smi`, régi `.img` / `.dc42` lemezképek, valamint az iOS-appok (`.ipa`).
    Felismerés MIME-típus alapján is (pl. `application/x-apple-diskimage`, `application/x-xar`); a `.command` /
    `.tool` szkriptek shell-szkriptek, ezeknél csak figyelmeztetés. Linuxon nem futtathatók (a Darling kísérleti,
    grafikus appokat nem visz), ezért
    érthető üzenet: „Ez a program Mac-re készült, ezen a gépen nem fut”; ha az app megvan Flathubon (pl.
    Spotify, Discord, VS Code), a Linuxos változatát egy kattintással felajánljuk; a benne lévő fájlok
    (betűtípus, dokumentum) az Ark-kal kicsomagolhatók

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
    az első lapon átváltható. A Sloth Központ is le van fordítva mind az 50 nyelvre.
    Hátravan: anyanyelvi átnézés (a fordításokat MI készítette)
  - [x] A végén gyors gombok: Steam-bejelentkezés, online fiókok, nyelv és régió (a nyelvet a telepítő kérdezi)
  - [x] Az ArtCraft frissítése: felhasználói telepítés + napi háttérfrissítő (`sloth-github-bundle-update.timer`, SHA256 ellenőrzéssel); VM-ben még tesztelni
- [ ] **Sloth Központ** (egy app, modulokra bontva; `files/system/usr/lib/sloth-os/sloth-center/`):
  - [x] Frissítések és visszaállítás (keresés, telepítés folyamatjelzővel, újraindítás, vissza az előzőre, a mostani verzió megtartása; VM-ben még tesztelni);
    a gépen lévő összes verzió listája: bármelyik indítható legközelebb letöltés nélkül (`ostree admin set-default`),
    és egyenként megtartható
  - [x] Driverek és hardver: videókártya felismerése, NVIDIA ↔ AMD/Intel változat váltása (`rpm-ostree rebase`),
    Secure Boot kulcs regisztrálása lépésenkénti útmutatóval (`mokutil`); VM-ben és Secure Boot-os gépen még tesztelni.
    Kontrollerek: a csatlakoztatottak listája (kábel / Bluetooth, akkuszint), párosítás és a gombok kipróbálása
    a KDE moduljaival. Megjegyzés: amíg a repó privát, a váltáshoz registry-bejelentkezés kell (Fejlesztői pult →
    Bejelentkezés a csomagtárolóba, 2026-10-19)
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
  - [x] Bejelentkezési módok a hardver alapján (Sloth Központ → Fiók és biztonság; csak az látszik, amihez megvan a
    hardver): ujjlenyomat (`fprintd`, felvétel a KDE Felhasználók moduljában, bekapcsolás `authselect`
    with-fingerprint), biztonsági kulcs (FIDO2/YubiKey: felvétel `pamu2fcfg`-vel, `authselect` with-pam-u2f), céges
    fiók (Active Directory: `realm join/leave` űrlapról). VM-ben és valódi hardveren még tesztelni.
    Hátravan: Entra ID, a jelszótároló nyitása jelszó nélküli belépésnél. Az eredeti terv:
  - [x] PIN-kód (2026-10-19; a PAM-rész Fedora 44 konténerben `pamtester`-rel kipróbálva:
    `tools/tests/pin_pam_test.sh`, 14/14; VM-ben a bejelentkező és a zárolási képernyőn még megnézni): Sloth Központ →
    Fiók és biztonság, 4–8 számjegy, a könnyen kitalálhatók (1111, 1234…) tiltva. Saját authselect-profil
    (`vendor/sloth` = a Fedora `local` + with-sloth-pin, `files/scripts/pin-authselect.sh`); a pam_unix elé egy
    `pam_exec` sor kerül (`/usr/libexec/sloth-os/pin-check`), így ugyanabba a mezőbe a jelszó és a PIN is beírható.
    A PIN scrypt-hashként a `/etc/sloth-os/pin/<felhasználó>.json`-ban (`sloth-helper pin-set/pin-remove`); csak
    helyi szolgáltatásokban fogadjuk el (bejelentkezés, zárolási képernyő, jóváhagyás), távolról (ssh) soha;
    5 hibás próba után egyre hosszabb várakozás (legfeljebb 1 óra), közben a jelszó működik. TPM-es tárolás: később
  - [x] Arcfelismerés: döntés (2026-10-19), egyelőre nem építjük be. A Howdy csak személyes COPR-okból érhető el,
    és a PAM-ba kerülne (egy hibája a bejelentkezést érinti); ha van infrakamera, a Fiók és biztonság oldal ezt
    elmagyarázza, és a PIN-t vagy az ujjlenyomatot ajánlja. Újranézni, ha a Fedorába bekerül egy karbantartott megoldás
  - Bejelentkezési módok a hardver alapján (varázsló + Sloth Központ; a gép felismeri, mit tud, és csak azt kínálja fel):
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
- [x] **Játékok:** játékonkénti beállítások (FPS-kijelző: MangoHud, felskálázás: gamescope FSR, teljesítmény mód:
  GameMode) Proton/Wine szavak nélkül (Sloth Központ → Játékok). Steames játékoknál az indítási beállításokba kerül
  (`localconfig.vdf`, a felhasználó saját beírásai megmaradnak; csak zárt Steamnél írható, a felület bezárja),
  Windows-programoknál a program adatai közé (`.sloth/app.json`), és a .exe kezelő indításkor alkalmazza
  (`sloth_common/gamesettings.py`). VM-ben és valódi játékkal még tesztelni

### Meglévő KDE / Flatpak GUI-k (ellenőrizni, hogy benne vannak-e az image-ben)
Döntés (2026-10-15): az image-ben csak az marad, ami a rendszer működéséhez elengedhetetlen; a többi
a Discoverből telepíthető. Ami marad: Partíciókezelő, Rendszerfigyelő, Dolphin, Konsole, Discover,
Rendszerbeállítások, KWrite, Ark, Spectacle, tűzfal-beállítás, nyomtatók, Bluetooth, Orca képernyőolvasó,
jelszótároló (KWallet), a kínai/japán/koreai beviteli módok, `podman` + `skopeo`, és amit a saját eszközeink
használnak. **A hibaelhárításhoz szükséges eszközök is maradnak** (a napi használathoz nem kell terminál, de ha
valami elromlik, legyen mivel megjavítani): naplónéző (kjournald), Filelight (mi foglalja a lemezt), `nano`, `vim`,
`htop`, `nvtop`, `tmux` (szöveges konzolon is), távsegítség (KRdp / krfb).
- [x] A többi kivétele (`files/scripts/slim-image.sh`, a modulok végén): Kate (a KWrite marad), KDE Connect,
  Súgóközpont, `just` (az `ublue-os-just`-tal), `toolbox` (a `distrobox` marad), `buildah`, `cosign`, `ibus` (a
  fcitx5 marad, vele is megvan a kínai/japán/koreai bevitel), a KDE és a Fedora háttérképei, a BlueBuild
  nushell-bővítményei. Csomagonként ellenőrizve, mi függ tőlük; helyben kipróbálva: a `/usr` 9612 → 8751 MB.
  A `git` marad (eldönteni). VM-ben még megnézni, hogy minden megvan-e, ami kell
- [ ] Appok és frissítések: Discover · Flatpak jogosultságok: Rendszerbeállítások
- [ ] Tűzfal (`firewall-cmd`): Rendszerbeállítások tűzfal modul
- [ ] Partíciók (`fdisk`, `mkfs`): KDE Partíciókezelő
- [ ] Folyamatok (`top`, `kill`): Rendszerfigyelő
- [ ] Hálózat, VPN, nyomtatók, felhasználók, gépnév: Rendszerbeállítások

### Fejlesztői pult (a Sloth OS fejlesztéséhez) – kész 2026-10-19 (valódi gépen még tesztelni)
Sloth Központ → Fejlesztői pult (`sloth_center/devpanel.py`), terminál, `gh` és `cosign` nélkül (a GitHub REST API-t
közvetlenül hívja; a GitHub-hívások élesben kipróbálva):
- [x] Kapcsolat: repó és GitHub-token; a tokent egy gomb a GitHubon, előre kitöltött jogokkal hozza létre (repo,
  workflow, read:packages); a jelszótárolóba kerül (`secret-tool`; ha nincs, egy csak a felhasználó által olvasható fájl)
- [x] Buildek: a legutóbbi futások állapota, image és ISO build indítása, megnyitás a GitHubon, havi Actions-percek
  (ha a token és a fiók engedi)
- [x] Aláíró kulcs: be van-e állítva a `SIGNING_SECRET`; új kulcspár a cosign-nal Podmanben; a `cosign.pub`-ot a pult
  commitolja, a titkos kulcsot a vágólapra teszi, és megnyitja a GitHub titok-oldalát (a titok közvetlen feltöltéséhez
  libsodium kellene). Kulcscserénél figyelmeztet: a telepített gépek frissítése addig áll, amíg az új kulcs egy még a
  régivel aláírt frissítéssel el nem jut hozzájuk
- [x] Kipróbálás: bejelentkezés a csomagtárolóba (`sloth-helper registry-login`, `/etc/ostree/auth.json`), átállás egy
  buildre (`<commit>-<Fedora-verzió>` címke, rpm-ostree rebase) és vissza a legfrissebbre, virtuális gép (GNOME Boxes)

## 4. fázis – Kiadás
- [ ] Repó publikussá tétele, napi automatikus build visszakapcsolása (`.github/workflows/build.yml`)
- [ ] **Saját Sloth OS telepítő** (`iso/`): élő rendszer a pendrive-ról, kipróbálás telepítés nélkül, Anaconda nélkül
  - [x] Első változat: nyelv (az Üdvözlő 50 nyelve), billentyűzet, időzóna, egész lemezre telepítés
    (saját particionálás + `bootc install to-filesystem`, az image az ISO-ban van, internet nélkül is megy),
    folyamatjelző, újraindítás; a fiókot is a telepítő kérdezi meg (első induláskor jön létre). Építés:
    `tools/build-iso.sh` (Linux) vagy `tools/build-iso.ps1` (Windows), helyben Podmannel, vagy `.github/workflows/iso.yml`
  - [x] A telepítő mind az 50 nyelven
  - [x] Teljes képernyős „Kipróbálom / Telepítem” választó; kipróbáláshoz böngésző az élő rendszerben
    (2026-10-15 óta Falkon; a telepített rendszerbe nem kerül böngésző, az Üdvözlőben választ a felhasználó)
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
  - [x] ISO-build podman commit nélkül (2026-10-15): a telepítendő image kicsomagolt tárolója külön mappába kerül
    (`iso/payload.sh`), és az ISO készítésekor csatoljuk az élő rendszerbe. A lassú gépen egymaga másfél órás
    commit kimarad. A régi úton a `mksquashfs` kb. 1000 törlés-jelölést kihagyott („Cannot stat … ignoring”);
    ez a telepítést valószínűleg nem rontotta el (a rétegeket a tároló a `tar-split` fejlécekből rakja össze),
    az új úton pedig a törlés-jelölések `.wh.` fájlként megmaradnak (kipróbálva, a rétegek ellenőrző összege
    squashfs és overlay után is stimmel). VM-ben még tesztelni
  - [x] Negyedik VM-teszt (2026-10-15, Hyper-V, 2. generációs VM): a `bootc` végigment („Installation complete!”),
    utána a segéd log nélkül leállt („Installation failed”). Ok: a `bootc` a végén csak olvashatóra csatolja
    vissza a célt, és a boot menü beállítása (`custom.cfg`) kivételt dobott. Javítva: írás előtt visszacsatolja
    írhatóra, és a segéd minden váratlan hibát a logba ír. VM-ben újra megnézni
  - [x] Telepítés közben nem kapcsol le a képernyő, nem zárol és nem alszik el a gép (élő rendszer beállításai a
    `livesys-session-extra`-ban + a telepítő D-Bus tiltása a telepítés idejére); új ISO-val még tesztelni
  - [x] `tools/build-iso.ps1`: a `build-iso.sh`-t futtatja közvetlenül a Podman gép WSL-disztribúciójában (eddig
    kétszer töltötte le az image-et, és a Windows → ssh → Podman út nagy terhelésnél elakadt); a WSL-hez
    cgroupfs és cgroup nélküli konténerek kellenek (a `build-iso.sh` magától állítja)
  - [x] Helytakarékos ISO-build (2026-10-19; a teljes ISO-buildet még lefuttatni): az átmeneti OCI-másolat
    (kb. 12 GB) kimarad, a kicsomagoló közvetlenül a letöltött tárolóból olvas (becsatolva,
    `containers-storage:[overlay@…]` forrásként; WSL-es Podmanben kis image-en kipróbálva). A csúcs így kb. 25–28 GB.
    A CI sem tölti le kétszer az image-et. A kicsomagolt példány hardlinkelése a letöltött rétegekre kimaradt
    (a containers/storage saját fájljai, túl kockázatos)
  - [ ] ISO méret (2026-10-15: 6,9 GB, ebből a squashfs 6,2 GB; zstd-19 marad). A következő ISO-n megnézni:
    - [x] Csak a Sloth OS saját háttérképei maradnak, a BlueBuild nushell-bővítményei kikerülnek
      (`files/scripts/slim-image.sh`; a telepített rendszer is kisebb lesz)
    - [x] Firefox helyett Falkon az élő rendszerben (döntés: 2026-10-15): KDE, QtWebEngine/Chromium alapú; RPM,
      a QtWebEngine már benne van az image-ben, így kb. 14 MB a Firefox Flatpak kb. 0,5 GB-ja helyett.
      Csak az élő rendszerbe kerül (`iso/build.sh`); internet nélküli telepítésnél nem másolunk böngészőt,
      a felhasználó az Üdvözlőben választ (most 9 böngésző)
    - [x] A telepítendő image rétegeinek összevonása egy rétegbe, kapcsolóval (2026-10-19): `SLOTH_SQUASH=1`
      (`tools/build-iso.sh`), `-Squash` (`tools/build-iso.ps1`), `squash` (CI). A lecserélt / törölt fájlok (pl. a
      régi kernel) kiesnek; becslés: 0,5–1 GB. Ára: az első frissítés a teljes image-et tölti le, ezért alapból ki;
      kiadáshoz. A következő ISO-n megmérni, mennyit hoz
  - [x] Windows mellé telepítés (2026-10-15; valódi Windowszal még tesztelni): a lemezválasztóban Windowsos
    lemeznél „Windows mellé” (alapból) vagy „az egész lemez törlése”, méretcsúszkával. A segéd felméri a lemezt
    (`sloth-install-helper probe`): UEFI és GPT kell; a meglévő szabad hely, ha elég, különben a legnagyobb
    NTFS-partíció (C:) zsugorítása `ntfsresize`-zal (a Windowsnak marad 20 GB szabad hely). A Sloth OS saját EFI
    partíciót kap (a Windowséhoz nem nyúl), a boot menü látszik, benne a Windows (`EFI/fedora/sloth-windows.cfg`,
    bármelyik lemezen lévő Windows-rendszerindítóra), a hardveróra helyi időben jár. Felismeri és érthetően
    magyarázza: BitLocker (a Windowsban kell helyet felszabadítani; a helyreállítási kulcsra figyelmeztet),
    gyors indítás / hibernálás (a `hiberfil.sys` fejlécéből), esedékes lemezellenőrzés, BIOS mód, MBR-es lemez,
    kevés hely. Loop eszközön kipróbálva: zsugorítás (a fájlok épek, a partíció kezdete változatlan), szabad
    hely, hibernált Windows, BitLocker szabad hellyel és anélkül. Hátravan: VM-ben a teljes telepítés és a
    boot menü Windows-bejegyzése
    - [x] Boot-sorrend védelme (`sloth-boot-order.service`): ha egy Windows-frissítés a „Windows Boot Manager”-t a
      sorrend elejére tette, a Sloth OS következő indításakor visszakerül az első helyre (mást, pl. egy előre tett
      pendrive-ot nem bánt). Korlát: addig a gép a Windowst indítja; a Sloth OS-t egyszer a gép saját
      indítómenüjéből kell választani. Ezt a Windows-oldali segéd (2026-10-19, lásd fent a teendőknél) megakadályozza
  - [x] NVIDIA-s gépen automatikusan az NVIDIA-s változat (2026-10-15; valódi NVIDIA-s gépen még tesztelni): a
    telepítő ISO-n csak az AMD/Intel-es fér el, ezért a telepített rendszer intézi: `sloth-nvidia-auto.timer`
    (indítás után 2 perccel, utána óránként, amíg nem sikerül) NVIDIA-kártyánál a háttérben `rpm-ostree rebase`
    az NVIDIA-s image-re, Secure Bootnál a kulcs regisztrálását is előkészíti; egyszer fut (a kézi visszaváltást
    nem írja felül). Értesítés a felhasználónak (`sloth-nvidia-notify`): „Újraindítás most” vagy a Sloth Központ
    Driverek oldalának útmutatója (`sloth-center --page drivers`)
  - [x] Telepítés után a frissítések aláírás-ellenőrzéssel (`ostree-image-signed`; 2026-10-16, valódi gépen még
    tesztelni): mindkét image elfogadja a másik változat aláírását is (`files/scripts/signing-family.sh` a signing
    modul után; különben az AMD/Intel <-> NVIDIA váltás elakadna). A telepítő az aláírt hivatkozást írja be, ha a
    policy.json aláírást követel (különben marad a régi, hogy legyen frissítés). A régebbi telepítéseket a
    `sloth-signed-updates.timer` egyszer átállítja (az előkészített, újraindításra váró változatot is)
  - [x] Lemeztitkosítás (2026-10-16; VM-ben és valódi gépen még tesztelni, főleg az indításkori jelszókérőt): a
    lemezválasztóban „A lemez titkosítása” (alapból a fiók jelszavával, vagy külön jelszóval; legalább 8 karakter),
    teljes lemezen és Windows mellett is. LUKS2 a rendszerpartíción (TRIM engedélyezve), külön titkosítatlan
    /boot (1 GB; a GRUB a LUKS2-t nem tudja kinyitni), `rd.luks.uuid` és crypttab. A jelszókérő a választott
    billentyűzetkiosztással fut (`rd.vconsole.keymap`; az initramfs-ben minden kiosztás:
    `/usr/lib/dracut/dracut.conf.d/90-sloth-luks.conf`), a Plymouth-téma szöveg helyett lakat ikont mutat (a
    systemd szövege angol és technikai). Loop eszközön kipróbálva: jó/rossz jelszó, LUKS2, TRIM, /boot, crypttab,
    a fájlrendszer kitölti a partíciót. Közben javítva: Windows mellett a szabad hely egészét elfoglalta a
    választott méret helyett
  - [ ] Régi (BIOS-os) gépek
  - [ ] ISO letöltése: privát repóban a 2 GB-os kiadás- és 500 MB-os tárhelykorlát miatt csak publikussá tétel után
- [ ] Weboldal, letöltés, dokumentáció
