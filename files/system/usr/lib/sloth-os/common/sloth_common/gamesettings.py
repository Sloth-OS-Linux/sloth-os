"""Játékonkénti beállítások: FPS-kijelző (MangoHud), teljesítmény mód (GameMode), felskálázás (gamescope, FSR).

Közös rész a Sloth Központ (beállítás) és a .exe kezelő (indítás) számára. A beállítás egy kis
szótár: {"fps": bool, "performance": bool, "upscale": "off" | "quality" | "balanced" | "performance"}.
A Steames játékoknál ebből az indítási beállítások elejére kerülő parancs lesz, a Windows-programoknál
a .exe kezelő ebből rakja össze az indítást. A felhasználó a "Proton", "Wine" szavakat nem látja.
"""
import re
import shlex

UPSCALE_SCALES = {"quality": 0.77, "balanced": 0.67, "performance": 0.5}
DEFAULTS = {"fps": False, "performance": False, "upscale": "off"}
OUR_COMMANDS = ("mangohud", "gamemoderun", "gamescope")


def normalize(settings):
    s = {**DEFAULTS, **(settings or {})}
    s["fps"], s["performance"] = bool(s["fps"]), bool(s["performance"])
    if s["upscale"] not in UPSCALE_SCALES:
        s["upscale"] = "off"
    return {k: s[k] for k in DEFAULTS}


def wrapper(settings, screen):
    """A program elé kerülő parancsok listája. screen: (szélesség, magasság) képpontban."""
    s = normalize(settings)
    cmd = []
    if s["upscale"] != "off" and screen and screen[0] > 0:
        w, h = screen
        scale = UPSCALE_SCALES[s["upscale"]]
        cmd += ["gamescope", "-w", str(int(w * scale)), "-h", str(int(h * scale)),
                "-W", str(w), "-H", str(h), "-F", "fsr", "-f", "--"]
    if s["performance"]:
        cmd.append("gamemoderun")
    if s["fps"]:
        cmd.append("mangohud")
    return cmd


# --- Steam indítási beállítások ("... %command% ...") ---------------------------------------

def parse_launch_options(text):
    """Az indítási beállításból kiolvassa a mi beállításainkat, és visszaadja a felhasználó saját részét.

    -> (settings, előtte maradó saját szavak, a %command% utáni rész)
    """
    text = (text or "").strip()
    if "%command%" not in text:
        # régi forma: csak argumentumok a játéknak (pl. "-dx11")
        return dict(DEFAULTS), [], text
    before, after = text.split("%command%", 1)
    try:
        words = shlex.split(before)
    except ValueError:
        return dict(DEFAULTS), [], text
    settings, rest, i = dict(DEFAULTS), [], 0
    while i < len(words):
        w = words[i]
        if w == "gamescope" and "--" in words[i:]:
            end = words.index("--", i)
            args = words[i + 1:end]
            if "-w" in args and "-W" in args:
                try:
                    ratio = int(args[args.index("-w") + 1]) / int(args[args.index("-W") + 1])
                    settings["upscale"] = min(UPSCALE_SCALES, key=lambda k: abs(UPSCALE_SCALES[k] - ratio))
                except (ValueError, IndexError, ZeroDivisionError):
                    pass
            i = end + 1
            continue
        if w == "gamemoderun":
            settings["performance"] = True
        elif w == "mangohud":
            settings["fps"] = True
        else:
            rest.append(w)
        i += 1
    return settings, rest, after.strip()


def build_launch_options(settings, rest, after, screen):
    # A változóbeállítások (pl. DXVK_HUD=1) a sor elejére valók, a mi parancsaink utánuk jönnek
    env = [w for w in rest if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w)]
    others = [w for w in rest if w not in env]
    words = env + wrapper(settings, screen) + others
    if not words and not after:
        return ""
    return " ".join([shlex.join(words)] if words else []) + (" " if words else "") + "%command%" + \
        (" " + after if after else "")
