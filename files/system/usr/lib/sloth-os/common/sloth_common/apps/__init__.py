"""A telepített alkalmazások közös kezelése (a .exe kezelő és a Sloth Központ is ezt használja).

  library  hol vannak a programok, és mi tartozik hozzájuk (mappák, adatok, áthelyezés, eltávolítás)
  menu     Start menü bejegyzések és ikonok
  winreg   a Windows-környezet registryjének olvasása (telepített programok adatai)
  detect   telepítés után: melyik program települt, és melyik fájllal indul
  steam    a Steam fájljai (játékkönyvtárak, a Steamhez hozzáadott programok)
  imports  máshol (Steam, Lutris, Bottles, ~/.wine) telepített programok átvétele

Qt nélküli Python: egységtesztelhető (tools/tests/), és a háttérfolyamatok is használhatják.
"""
