"""Per-game settings: FPS display (MangoHud), performance mode (GameMode), upscaling (gamescope, FSR).

A shared part for Sloth Center (settings) and the .exe handler (starting). The setting is a small
dictionary: {"fps": bool, "performance": bool, "upscale": "off" | "quality" | "balanced" | "performance"}.
For Steam games it becomes a command at the front of the launch options; for Windows programs
the .exe handler builds the start from it. The user does not see the words "Proton", "Wine".
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
    """The list of commands put in front of the program. screen: (width, height) in pixels."""
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


# --- Steam launch options ("... %command% ...") ---------------------------------------

def parse_launch_options(text):
    """Reads our settings out of the launch options, and returns the user's own part.

    -> (settings, the user's own words before it, the part after %command%)
    """
    text = (text or "").strip()
    if "%command%" not in text:
        # the old form: only arguments for the game (e.g. "-dx11")
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
    # Variable settings (e.g. DXVK_HUD=1) belong at the start of the line, our commands come after them
    env = [w for w in rest if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w)]
    others = [w for w in rest if w not in env]
    words = env + wrapper(settings, screen) + others
    if not words and not after:
        return ""
    return " ".join([shlex.join(words)] if words else []) + (" " if words else "") + "%command%" + \
        (" " + after if after else "")
