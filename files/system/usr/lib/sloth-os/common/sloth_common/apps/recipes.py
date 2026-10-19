"""Receptek: ismert programok bevált beállításai, adatként (nem kódként).

A receptek két helyről jönnek:
  - a rendszerrel (/usr/share/sloth-os/recipes.json: internet nélkül is megvannak),
  - a közös tudás repójából (bathorizsolt/sloth-os-knowledge, recipes.json), amit a sloth-windows-prepare
    a háttérben letölt; ha ez újabb, ez érvényes.
A receptfájlt kézzel szerkesztjük és ellenőrizzük (a knowledge repó Actionje validálja), és a gép is újra
ellenőrzi: csak az engedélyezett mezők és értékek fogadhatók el (tetszőleges parancs, környezeti változó,
paraméter vagy DLL-betöltés nem). A hibás recept kimarad, a többi működik.

Egy recept:
  {"id": "battlenet", "name": "Battle.net",
   "match": {"dirs": ["Program Files (x86)/Battle.net"], "exe": ["battle.net*.exe"]},
   "stubs": {"battle.net launcher.exe": "Battle.net.exe"},     rövid életű indító -> a kliens (a mappájához képest)
   "prefer": ["battle.net launcher.exe"], "skip": ["battle.net uninstaller.exe"],   a Start menühöz
   "verbs": [...], "env": [...], "args": [...], "dll_overrides": ["locationapi=d"],  minden .exe-re
   "per_exe": {"galaxyclient.exe": {"args": [...], "dll_overrides": [...], "env": [...], "verbs": [...]}}}
"""
import fnmatch
import json
import logging
import os
import re
from pathlib import Path

log = logging.getLogger("sloth-os.apps")

SYSTEM = Path("/usr/share/sloth-os/recipes.json")
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "recipes.json"
URL = "https://raw.githubusercontent.com/bathorizsolt/sloth-os-knowledge/main/recipes.json"

# Ugyanazok az összetevők és kapcsolók, mint a közös tudásban (services/knowledge/src/worker.js); ha ott
# bővül, itt is kell (és a knowledge repó seed/validate_recipes.py-jában)
ALLOWED_VERBS = {
    "d3dcompiler_42", "d3dcompiler_43", "d3dcompiler_46", "d3dcompiler_47", "d3dx10", "d3dx11_42", "d3dx11_43",
    "d3dx9", "dotnet48", "gdiplus", "mf", "mfc42", "msxml3", "msxml4", "msxml6", "physx", "riched20", "vb6run",
    "vcrun2005", "vcrun2008", "vcrun2010", "vcrun2012", "vcrun2013", "vcrun2022", "xact", "xinput",
}
ALLOWED_ENV = {
    "PROTON_USE_WINED3D", "PROTON_ENABLE_NVAPI", "PROTON_HIDE_NVIDIA_GPU", "PROTON_FORCE_LARGE_ADDRESS_AWARE",
    "PROTON_HEAP_DELAY_FREE", "PROTON_NO_D3D11", "PROTON_NO_D3D10", "PROTON_OLD_GL_STRING", "PROTON_NO_WRITE_WATCH",
    "PROTON_NO_FSYNC", "PROTON_NO_ESYNC",
}
# Programparaméterek: csak a bevált, ártalmatlan kapcsolók (a böngészőmotorok GPU-ja, frissítő kihagyása)
ALLOWED_ARGS = {"--disable-gpu", "-opengl", "-SkipBuildPatchPrereq", "/runWithoutUpdating", "/deelevated",
                "--in-process-gpu", "--disable-gpu-sandbox"}
# DLL-kikapcsolás (=d) vagy a beépített változat (=b); natív DLL betöltését recept nem kérheti
_DLL = re.compile(r"^[a-z0-9_.-]{1,40}=(d|b)$")
_EXE = re.compile(r"^[a-z0-9 ._()+*?\[\]-]{1,80}$")
_ID = re.compile(r"^[a-z0-9-]{1,40}$")
_KEYS = {"id", "name", "match", "stubs", "prefer", "skip", "verbs", "env", "args", "dll_overrides", "per_exe"}
_PER_EXE_KEYS = {"verbs", "env", "args", "dll_overrides"}


def _rel_ok(path, allow_up=False):
    """Relatív út a Windows-környezeten belül (a „..” csak a kliens keresésénél, egy szinttel feljebb)."""
    if not isinstance(path, str) or not path or len(path) > 200 or path.startswith(("/", "\\")) or ":" in path:
        return False
    parts = re.split(r"[\\/]", path)
    ups = sum(1 for p in parts if p == "..")
    return (ups == 0 or (allow_up and ups <= 2 and all(p == ".." for p in parts[:ups]))) and "" not in parts


def _settings_ok(d):
    return (set(d) <= _PER_EXE_KEYS
            and set(d.get("verbs", [])) <= ALLOWED_VERBS
            and set(d.get("env", [])) <= ALLOWED_ENV
            and set(d.get("args", [])) <= ALLOWED_ARGS
            and all(isinstance(o, str) and _DLL.match(o) for o in d.get("dll_overrides", []))
            and all(isinstance(d.get(k, []), list) for k in _PER_EXE_KEYS))


def validate(recipe):
    """Igaz, ha a recept minden mezője megengedett. (A knowledge repó ellenőrzője ugyanezt nézi.)"""
    try:
        if not isinstance(recipe, dict) or not set(recipe) <= _KEYS or not _ID.match(recipe.get("id", "")):
            return False
        if not isinstance(recipe.get("name", ""), str) or len(recipe.get("name", "")) > 80:
            return False
        match = recipe.get("match") or {}
        if not set(match) <= {"dirs", "exe"} or not (match.get("dirs") or match.get("exe")):
            return False
        if not all(_rel_ok(d) for d in match.get("dirs", [])) or not all(
                isinstance(e, str) and _EXE.match(e) for e in match.get("exe", [])):
            return False
        stubs = recipe.get("stubs", {})
        if not isinstance(stubs, dict) or not all(
                _EXE.match(k.split("/")[-1]) and k.count("/") <= 1 and _rel_ok(v, allow_up=True)
                for k, v in stubs.items()):
            return False
        for key in ("prefer", "skip"):
            if not all(isinstance(e, str) and _EXE.match(e) for e in recipe.get(key, [])):
                return False
        if not _settings_ok({k: recipe[k] for k in _PER_EXE_KEYS if k in recipe}):
            return False
        per = recipe.get("per_exe", {})
        return isinstance(per, dict) and all(_EXE.match(k) and isinstance(v, dict) and _settings_ok(v)
                                             for k, v in per.items())
    except (TypeError, AttributeError):
        return False


def _read(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and data.get("version") == 1 else None
    except (OSError, ValueError):
        return None


_cache = None


def load(paths=None):
    """Az érvényes receptek. A letöltött fájl akkor nyer, ha újabb (updated mező), mint a rendszerrel jövő."""
    global _cache
    if paths is None and _cache is not None:
        return _cache
    files = [d for d in (_read(p) for p in (paths or [SYSTEM, CACHE])) if d]
    best = max(files, key=lambda d: str(d.get("updated", "")), default={"recipes": []})
    out = []
    for r in best.get("recipes", []):
        if validate(r):
            out.append(r)
        else:
            log.warning("érvénytelen recept, kihagyva: %s", r.get("id") if isinstance(r, dict) else r)
    if paths is None:
        _cache = out
    return out


def _glob(name, patterns):
    return any(fnmatch.fnmatch(name.lower(), p.lower()) for p in patterns)


def matching(prefix, exe):
    """A programra (a Windows-környezete és a .exe alapján) illő receptek."""
    drive_c = Path(prefix) / "drive_c"
    name = Path(exe).name
    out = []
    for r in load():
        m = r["match"]
        if _glob(name, m.get("exe", [])) or any((drive_c / d).is_dir() for d in m.get("dirs", [])):
            out.append(r)
    return out


def settings(prefix, exe):
    """Az indításhoz: {"verbs", "env", "args", "dll_overrides"} az illő receptekből (a .exe-re szólóval együtt)."""
    out = {k: [] for k in _PER_EXE_KEYS}
    name = Path(exe).name.lower()
    for r in matching(prefix, exe):
        parts = [r] + [v for k, v in r.get("per_exe", {}).items() if fnmatch.fnmatch(name, k.lower())]
        for part in parts:
            for k in _PER_EXE_KEYS:
                out[k] += [v for v in part.get(k, []) if v not in out[k]]
    return out


def stub_target(exe):
    """Rövid életű indító helyett a kliens útja (ha egy recept ismeri), vagy None."""
    exe = Path(exe)
    keys = (f"{exe.parent.name}/{exe.name}".lower(), exe.name.lower())
    for r in load():
        for k, v in r.get("stubs", {}).items():
            if k.lower() in keys:
                return Path(os.path.normpath(exe.parent / v))
    return None


def preferences(prefix):
    """A Start menühöz: (előnyben részesített, kihagyandó) .exe-nevek mintái a környezetre illő receptekből."""
    drive_c = Path(prefix) / "drive_c"
    prefer, skip = [], []
    for r in load():
        if any((drive_c / d).is_dir() for d in r["match"].get("dirs", [])):
            prefer += r.get("prefer", [])
            skip += r.get("skip", [])
    return prefer, skip
