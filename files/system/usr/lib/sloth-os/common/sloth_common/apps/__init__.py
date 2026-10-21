"""Shared management of installed applications (the .exe handler and Sloth Center both use it).

  library  where the programs are, and what belongs to them (folders, data, moving, removing)
  menu     Start menu entries and icons
  winreg   reading the registry of a Windows environment (data of installed programs)
  detect   after installing: which program got installed, and which file starts it
  steam    Steam's files (game libraries, programs added to Steam)
  imports  taking over programs installed elsewhere (Steam, Lutris, Bottles, ~/.wine)

Python without Qt: unit-testable (tools/tests/), and background processes can use it too.
"""
