#!/usr/bin/env python3
"""A Sloth OS Plasma színsémáinak generátora.

Használat: python3 gen_colors.py <kimeneti mappa>
(a repóban: files/system/usr/share/color-schemes)

Minden séma tompított, nem harsány színekből áll. Egy sémához elég megadni a fő
felületek színeit; a többit (státuszszínek, kiegészítő csoport, ablakkeret)
a generátor tölti ki.
"""
import sys

# Státuszszínek (link, hiba, figyelmeztetés, siker) sötét és világos sémákhoz
STATUS_DARK = dict(link="#8fb0cf", visited="#b49ccf", negative="#e06c75", neutral="#e5b567", positive="#7fbf8a")
STATUS_LIGHT = dict(link="#2f6aa3", visited="#7a4fa8", negative="#c0392b", neutral="#b7791f", positive="#2e8540")

SCHEMES = {
    # Az alapértelmezett: grafit alap, matt ezüst kiemelés (a logóhoz illik)
    "SlothSilverDark": dict(
        name="Sloth Silver (sötét)", dark=True,
        window="#2b2d31", window_alt="#313338", view="#222427", view_alt="#2a2c30",
        button="#373a3f", button_alt="#3e4147", header="#25272a", header_inactive="#2b2d31",
        tooltip="#1f2124", fg="#e3e5e8", fg_inactive="#9aa0a7",
        sel="#b4b9c0", sel_alt="#a6abb3", sel_fg="#1c1e21", focus="#b4b9c0", hover="#cfd3d8"),
    "SlothSilverLight": dict(
        name="Sloth Silver (világos)", dark=False,
        window="#e3e5e8", window_alt="#dcdfe3", view="#f4f5f7", view_alt="#eceef1",
        button="#d6d9de", button_alt="#cdd1d6", header="#d8dbdf", header_inactive="#e3e5e8",
        tooltip="#f4f5f7", fg="#23262a", fg_inactive="#666c74",
        sel="#68707b", sel_alt="#737b86", sel_fg="#ffffff", focus="#68707b", hover="#858c96"),
    "SlothWhite": dict(
        name="Sloth Hófehér", dark=False,
        window="#f6f7f8", window_alt="#eff1f3", view="#ffffff", view_alt="#f6f7f9",
        button="#eceef1", button_alt="#e4e7eb", header="#f0f2f4", header_inactive="#f6f7f8",
        tooltip="#ffffff", fg="#1f2328", fg_inactive="#6b7179",
        sel="#5b6573", sel_alt="#677180", sel_fg="#ffffff", focus="#5b6573", hover="#7a8492"),
    "SlothBlack": dict(
        name="Sloth Éjfekete", dark=True,
        window="#121315", window_alt="#17181b", view="#0b0c0d", view_alt="#131416",
        button="#1d1f22", button_alt="#232528", header="#0e0f11", header_inactive="#121315",
        tooltip="#0b0c0d", fg="#e6e7e9", fg_inactive="#8e939a",
        sel="#c9cdd2", sel_alt="#b9bdc3", sel_fg="#0e0f11", focus="#c9cdd2", hover="#e0e3e6"),
    # Tompított világoskék: látszik, hogy kék, de nem bántó
    "SlothMist": dict(
        name="Sloth Ködkék", dark=False,
        window="#dfe6ed", window_alt="#d7dfe7", view="#eef2f6", view_alt="#e6ecf1",
        button="#d2dbe4", button_alt="#c9d3dd", header="#d5dee7", header_inactive="#dfe6ed",
        tooltip="#eef2f6", fg="#1f2a35", fg_inactive="#5f6d7b",
        sel="#56728f", sel_alt="#617d99", sel_fg="#ffffff", focus="#56728f", hover="#7893ad"),
    "SlothNight": dict(
        name="Sloth Éjkék", dark=True,
        window="#1f2630", window_alt="#252d38", view="#19202a", view_alt="#202833",
        button="#2a333f", button_alt="#313b48", header="#1a2129", header_inactive="#1f2630",
        tooltip="#161c24", fg="#dde4ec", fg_inactive="#8d99a7",
        sel="#8aa5bf", sel_alt="#7d98b2", sel_fg="#121820", focus="#8aa5bf", hover="#a7bdd2"),
    "SlothSage": dict(
        name="Sloth Zsálya", dark=False,
        window="#e1e7e0", window_alt="#d9e0d8", view="#f0f3ef", view_alt="#e8ece7",
        button="#d4dcd3", button_alt="#cbd4ca", header="#d7dfd6", header_inactive="#e1e7e0",
        tooltip="#f0f3ef", fg="#212a23", fg_inactive="#606c62",
        sel="#56715b", sel_alt="#617c66", sel_fg="#ffffff", focus="#56715b", hover="#7a937e"),
}

DEFAULT = "SlothSilverDark"


def rgb(h):
    h = h.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def build(sid, c):
    st = STATUS_DARK if c["dark"] else STATUS_LIGHT

    def group(bg, bg_alt, fg=None, fg_inactive=None, fg_active=None):
        fg = fg or c["fg"]
        return {
            "BackgroundNormal": bg, "BackgroundAlternate": bg_alt,
            "DecorationFocus": c["focus"], "DecorationHover": c["hover"],
            "ForegroundNormal": fg, "ForegroundInactive": fg_inactive or c["fg_inactive"],
            "ForegroundActive": fg_active or c["hover"],
            "ForegroundLink": st["link"], "ForegroundVisited": st["visited"],
            "ForegroundNegative": st["negative"], "ForegroundNeutral": st["neutral"],
            "ForegroundPositive": st["positive"],
        }

    groups = {
        "Colors:Window": group(c["window"], c["window_alt"]),
        "Colors:View": group(c["view"], c["view_alt"]),
        "Colors:Button": group(c["button"], c["button_alt"]),
        "Colors:Header": group(c["header"], c["window_alt"]),
        "Colors:Header][Inactive": group(c["header_inactive"], c["window_alt"]),
        "Colors:Tooltip": group(c["tooltip"], c["window_alt"]),
        # Kiegészítő (pl. bejelentkező képernyő): mindig sötét
        "Colors:Complementary": {**group("#1c1e21", "#25272a", "#e3e5e8", "#9aa0a7", "#cfd3d8"),
                                 **{k: v for k, v in zip(
                                     ("ForegroundLink", "ForegroundVisited", "ForegroundNegative",
                                      "ForegroundNeutral", "ForegroundPositive"),
                                     STATUS_DARK.values())}},
        "Colors:Selection": group(c["sel"], c["sel_alt"], c["sel_fg"], c["sel_fg"], c["sel_fg"]),
    }

    lines = ["# Sloth OS színséma. Generálva: tools/branding/gen_colors.py – ne kézzel szerkeszd.", "",
             "[General]", f"ColorScheme={sid}", f"Name={c['name']}", "shadeSortColumn=true", "",
             "[KDE]", "contrast=4", ""]
    for g, kv in groups.items():
        lines.append(f"[{g}]")
        lines += [f"{k}={rgb(v)}" for k, v in kv.items()]
        lines.append("")
    lines += ["[WM]",
              f"activeBackground={rgb(c['header'])}", f"activeForeground={rgb(c['fg'])}",
              f"activeBlend={rgb(c['fg'])}", f"inactiveBackground={rgb(c['header_inactive'])}",
              f"inactiveForeground={rgb(c['fg_inactive'])}", f"inactiveBlend={rgb(c['fg_inactive'])}", ""]
    return "\n".join(lines)


def main():
    out = sys.argv[1]
    for sid, c in SCHEMES.items():
        with open(f"{out}/{sid}.colors", "w", encoding="utf-8") as f:
            f.write(build(sid, c))
        print("írva:", sid, "(alapértelmezett)" if sid == DEFAULT else "")


if __name__ == "__main__":
    main()
