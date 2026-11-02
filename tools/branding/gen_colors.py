#!/usr/bin/env python3
"""Generator of the Sloth OS Plasma color schemes.

Usage: python3 gen_colors.py <output folder>
(in the repository: files/system/usr/share/color-schemes)

Every scheme uses muted, not loud colors. For a scheme it is enough to give the colors of the main
surfaces; the rest (status colors, complementary group, window frame)
is filled in by the generator.
"""
import json
import sys
from pathlib import Path

# Status colors (link, error, warning, success) for dark and light schemes
STATUS_DARK = dict(link="#8fb0cf", visited="#b49ccf", negative="#e06c75", neutral="#e5b567", positive="#7fbf8a")
STATUS_LIGHT = dict(link="#2f6aa3", visited="#7a4fa8", negative="#c0392b", neutral="#b7791f", positive="#2e8540")

SCHEMES = {
    # The default: graphite base, matte silver highlight (it matches the logo)
    "SlothSilverDark": dict(
        name="Sloth Silver (dark)", dark=True,
        window="#2b2d31", window_alt="#313338", view="#222427", view_alt="#2a2c30",
        button="#373a3f", button_alt="#3e4147", header="#25272a", header_inactive="#2b2d31",
        tooltip="#1f2124", fg="#e3e5e8", fg_inactive="#9aa0a7",
        sel="#b4b9c0", sel_alt="#a6abb3", sel_fg="#1c1e21", focus="#b4b9c0", hover="#cfd3d8"),
    "SlothSilverLight": dict(
        name="Sloth Silver (light)", dark=False,
        window="#e3e5e8", window_alt="#dcdfe3", view="#f4f5f7", view_alt="#eceef1",
        button="#d6d9de", button_alt="#cdd1d6", header="#d8dbdf", header_inactive="#e3e5e8",
        tooltip="#f4f5f7", fg="#23262a", fg_inactive="#666c74",
        sel="#68707b", sel_alt="#737b86", sel_fg="#ffffff", focus="#68707b", hover="#858c96"),
    "SlothWhite": dict(
        name="Sloth Snow White", dark=False,
        window="#f6f7f8", window_alt="#eff1f3", view="#ffffff", view_alt="#f6f7f9",
        button="#eceef1", button_alt="#e4e7eb", header="#f0f2f4", header_inactive="#f6f7f8",
        tooltip="#ffffff", fg="#1f2328", fg_inactive="#6b7179",
        sel="#5b6573", sel_alt="#677180", sel_fg="#ffffff", focus="#5b6573", hover="#7a8492"),
    "SlothBlack": dict(
        name="Sloth Midnight Black", dark=True,
        window="#121315", window_alt="#17181b", view="#0b0c0d", view_alt="#131416",
        button="#1d1f22", button_alt="#232528", header="#0e0f11", header_inactive="#121315",
        tooltip="#0b0c0d", fg="#e6e7e9", fg_inactive="#8e939a",
        sel="#c9cdd2", sel_alt="#b9bdc3", sel_fg="#0e0f11", focus="#c9cdd2", hover="#e0e3e6"),
    # Muted light blue: you can tell it is blue, but it does not hurt
    "SlothMist": dict(
        name="Sloth Mist Blue", dark=False,
        window="#dfe6ed", window_alt="#d7dfe7", view="#eef2f6", view_alt="#e6ecf1",
        button="#d2dbe4", button_alt="#c9d3dd", header="#d5dee7", header_inactive="#dfe6ed",
        tooltip="#eef2f6", fg="#1f2a35", fg_inactive="#5f6d7b",
        sel="#56728f", sel_alt="#617d99", sel_fg="#ffffff", focus="#56728f", hover="#7893ad"),
    "SlothNight": dict(
        name="Sloth Night Blue", dark=True,
        window="#1f2630", window_alt="#252d38", view="#19202a", view_alt="#202833",
        button="#2a333f", button_alt="#313b48", header="#1a2129", header_inactive="#1f2630",
        tooltip="#161c24", fg="#dde4ec", fg_inactive="#8d99a7",
        sel="#8aa5bf", sel_alt="#7d98b2", sel_fg="#121820", focus="#8aa5bf", hover="#a7bdd2"),
    "SlothSage": dict(
        name="Sloth Sage", dark=False,
        window="#e1e7e0", window_alt="#d9e0d8", view="#f0f3ef", view_alt="#e8ece7",
        button="#d4dcd3", button_alt="#cbd4ca", header="#d7dfd6", header_inactive="#e1e7e0",
        tooltip="#f0f3ef", fg="#212a23", fg_inactive="#606c62",
        sel="#56715b", sel_alt="#617c66", sel_fg="#ffffff", focus="#56715b", hover="#7a937e"),
    # With real color (2026-11-02): you can tell the color at once; the text stays readable (at least 4.5 : 1)
    "SlothOcean": dict(
        name="Sloth Ocean Blue", dark=True,
        window="#162a3a", window_alt="#1b3245", view="#10202d", view_alt="#162838",
        button="#1f3a50", button_alt="#244259", header="#122331", header_inactive="#162a3a",
        tooltip="#0e1c27", fg="#e2eef7", fg_inactive="#8fa9bd",
        sel="#4fb0e6", sel_alt="#3fa2da", sel_fg="#071722", focus="#4fb0e6", hover="#7cc6ee"),
    "SlothForest": dict(
        name="Sloth Forest Green", dark=True,
        window="#1a2a20", window_alt="#203327", view="#13211a", view_alt="#1a2b21",
        button="#25392c", button_alt="#2b4233", header="#16241c", header_inactive="#1a2a20",
        tooltip="#111c16", fg="#e3efe6", fg_inactive="#93ab9a",
        sel="#5cbf7a", sel_alt="#4fb06d", sel_fg="#0b1a10", focus="#5cbf7a", hover="#86d39d"),
    "SlothSunset": dict(
        name="Sloth Sunset Orange", dark=True,
        window="#2e211c", window_alt="#362720", view="#241915", view_alt="#2d201b",
        button="#3d2c24", button_alt="#46322a", header="#281d18", header_inactive="#2e211c",
        tooltip="#1f1511", fg="#f5e9e2", fg_inactive="#b49c90",
        sel="#f08a4b", sel_alt="#e07a3b", sel_fg="#1f0f06", focus="#f08a4b", hover="#f5a877"),
    "SlothGrape": dict(
        name="Sloth Grape Purple", dark=True,
        window="#261f33", window_alt="#2d253c", view="#1d1828", view_alt="#251f31",
        button="#342b45", button_alt="#3b314e", header="#211b2c", header_inactive="#261f33",
        tooltip="#191422", fg="#ece6f5", fg_inactive="#a397b8",
        sel="#a57ee6", sel_alt="#956dd9", sel_fg="#140b22", focus="#a57ee6", hover="#bfa2ef"),
    "SlothRose": dict(
        name="Sloth Rose", dark=False,
        window="#f3e6ea", window_alt="#eddce2", view="#fbf4f6", view_alt="#f5eaee",
        button="#ebd8de", button_alt="#e3ccd4", header="#efdfe4", header_inactive="#f3e6ea",
        tooltip="#fbf4f6", fg="#33202a", fg_inactive="#735c67",
        sel="#b8406e", sel_alt="#c44f7b", sel_fg="#ffffff", focus="#b8406e", hover="#cf6f93"),
    "SlothAmber": dict(
        name="Sloth Amber", dark=False,
        window="#f4ead8", window_alt="#eee1ca", view="#fbf6ec", view_alt="#f5eddd",
        button="#ebdcc0", button_alt="#e3d1b2", header="#efe3cc", header_inactive="#f4ead8",
        tooltip="#fbf6ec", fg="#2f2414", fg_inactive="#726249",
        sel="#9a5f00", sel_alt="#a86a08", sel_fg="#ffffff", focus="#9a5f00", hover="#c08420"),
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
        # Complementary (e.g. login screen): always dark
        "Colors:Complementary": {**group("#1c1e21", "#25272a", "#e3e5e8", "#9aa0a7", "#cfd3d8"),
                                 **{k: v for k, v in zip(
                                     ("ForegroundLink", "ForegroundVisited", "ForegroundNegative",
                                      "ForegroundNeutral", "ForegroundPositive"),
                                     STATUS_DARK.values())}},
        "Colors:Selection": group(c["sel"], c["sel_alt"], c["sel_fg"], c["sel_fg"], c["sel_fg"]),
    }

    # the name in every language, from Sloth Welcome's translations ("scheme.<id>"), as in Welcome
    names = [f"Name[{code}]=Sloth {text}" for code, text in sorted(translated_names(sid).items())]
    lines = ["# Sloth OS color scheme. Generated by tools/branding/gen_colors.py – do not edit by hand.", "",
             "[General]", f"ColorScheme={sid}", f"Name={c['name']}", *names, "shadeSortColumn=true", "",
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


WELCOME_TRANSLATIONS = Path(__file__).resolve().parents[2] / "files/system/usr/lib/sloth-os/sloth-welcome/sloth_welcome/translations"


def translated_names(sid):
    """{language: name} of a scheme, without English (that is the default Name)."""
    out = {}
    for f in WELCOME_TRANSLATIONS.glob("*.json"):
        text = json.loads(f.read_text(encoding="utf-8")).get(f"scheme.{sid}")
        if text and f.stem != "en":
            out[f.stem] = text
    return out


def main():
    out = sys.argv[1]
    for sid, c in SCHEMES.items():
        with open(f"{out}/{sid}.colors", "w", encoding="utf-8") as f:
            f.write(build(sid, c))
        print("written:", sid, "(default)" if sid == DEFAULT else "")


if __name__ == "__main__":
    main()
