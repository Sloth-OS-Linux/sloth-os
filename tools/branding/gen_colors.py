import sys
out = sys.argv[1]
def rgb(h): h=h.lstrip('#'); return ",".join(str(int(h[i:i+2],16)) for i in (0,2,4))
STATUS = dict(link="#8fb0cf", visited="#b49ccf", negative="#e06c75", neutral="#e5b567", positive="#7fbf8a")
SCHEMES = {
 "SlothSilverDark": dict(name="Sloth Silver (sötét)",
   window="#2b2d31", window_alt="#313338", view="#222427", view_alt="#2a2c30",
   button="#373a3f", button_alt="#3e4147", header="#25272a", header_inactive="#2b2d31",
   tooltip="#1f2124", fg="#e3e5e8", fg_inactive="#9aa0a7",
   sel="#b4b9c0", sel_alt="#a6abb3", sel_fg="#1c1e21", focus="#b4b9c0", hover="#cfd3d8"),
 "SlothSilverLight": dict(name="Sloth Silver (világos)",
   window="#e3e5e8", window_alt="#dcdfe3", view="#f4f5f7", view_alt="#eceef1",
   button="#d6d9de", button_alt="#cdd1d6", header="#d8dbdf", header_inactive="#e3e5e8",
   tooltip="#f4f5f7", fg="#23262a", fg_inactive="#666c74",
   sel="#68707b", sel_alt="#737b86", sel_fg="#ffffff", focus="#68707b", hover="#858c96"),
}
light_status = dict(link="#2f6aa3", visited="#7a4fa8", negative="#c0392b", neutral="#b7791f", positive="#2e8540")
for sid, c in SCHEMES.items():
    st = light_status if "Light" in sid else STATUS
    def group(bg, bg_alt, fg=c["fg"], fg_inactive=c["fg_inactive"]):
        return {"BackgroundNormal": bg, "BackgroundAlternate": bg_alt,
                "DecorationFocus": c["focus"], "DecorationHover": c["hover"],
                "ForegroundNormal": fg, "ForegroundInactive": fg_inactive, "ForegroundActive": c["hover"] if fg==c["fg"] else fg,
                "ForegroundLink": st["link"], "ForegroundVisited": st["visited"],
                "ForegroundNegative": st["negative"], "ForegroundNeutral": st["neutral"], "ForegroundPositive": st["positive"]}
    groups = {
      "Colors:Window": group(c["window"], c["window_alt"]),
      "Colors:View": group(c["view"], c["view_alt"]),
      "Colors:Button": group(c["button"], c["button_alt"]),
      "Colors:Header": group(c["header"], c["window_alt"]),
      "Colors:Header][Inactive": group(c["header_inactive"], c["window_alt"]),
      "Colors:Tooltip": group(c["tooltip"], c["window_alt"]),
      "Colors:Complementary": group("#1c1e21", "#25272a", "#e3e5e8", "#9aa0a7"),
      "Colors:Selection": group(c["sel"], c["sel_alt"], c["sel_fg"], c["sel_fg"]),
    }
    lines = [f"# Sloth OS színséma – matt ezüst. Generálva; a színek a forrásban: tools/branding/gen_colors.py", ""]
    lines += ["[General]", f"ColorScheme={sid}", f"Name={c['name']}", "shadeSortColumn=true", "",
              "[KDE]", "contrast=4", ""]
    for g, kv in groups.items():
        lines.append(f"[{g}]")
        lines += [f"{k}={rgb(v)}" for k, v in kv.items()]
        lines.append("")
    lines += ["[WM]", f"activeBackground={rgb(c['header'])}", f"activeForeground={rgb(c['fg'])}",
              f"activeBlend={rgb(c['fg'])}", f"inactiveBackground={rgb(c['header_inactive'])}",
              f"inactiveForeground={rgb(c['fg_inactive'])}", f"inactiveBlend={rgb(c['fg_inactive'])}", ""]
    open(f"{out}/{sid}.colors", "w").write("\n".join(lines))
    print("írva:", sid)
