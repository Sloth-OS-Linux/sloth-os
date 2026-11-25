#!/usr/bin/python3
"""Steam games and the shared knowledge, end to end with the real Sloth Center code (in the Sloth OS image):
a fake Steam library with a game that "did not start", a knowledge.json with a ProtonDB setting for it, Sloth Center's
"Try a fix" (GamesController.tryFix), the game then running 5 minutes, the report queued with the games switch, and
sent by sloth-exe --maintenance's send_queue to a local server standing in for the knowledge service; the reports
it got are checked with the service's own validate() (services/knowledge/src/worker.js, run by node)."""
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

home = Path(tempfile.mkdtemp())
os.environ.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_STATE_HOME=str(home / ".state"),
                  XDG_CACHE_HOME=str(home / ".cache"), QT_QPA_PLATFORM="offscreen")
fakebin = home / "bin"
fakebin.mkdir()
for name in ("xdg-open", "steam", "flatpak"):
    (fakebin / name).write_text("#!/bin/sh\necho \"$0 $*\" >> %s/calls\n" % home)
    (fakebin / name).chmod(0o755)
os.environ["PATH"] = f"{fakebin}:{os.environ['PATH']}"
R = "/repo/files/system/usr/lib/sloth-os"
sys.path[:0] = [R + "/common", R + "/sloth-center", R + "/sloth-exe"]

APPID = "1091500"
ok = bad = 0


def check(desc, cond, got=""):
    global ok, bad
    if cond:
        ok += 1
        print("  OK:   ", desc)
    else:
        bad += 1
        print("  ERROR:", desc, got)


# a Steam library with the game (run through Proton: it has a compatdata folder)
root = home / ".local/share/Steam"
(root / "steamapps/compatdata" / APPID).mkdir(parents=True)
(root / f"steamapps/appmanifest_{APPID}.acf").write_text(
    '"AppState"\n{\n\t"appid"\t\t"%s"\n\t"name"\t\t"Test Game"\n}\n' % APPID)
local = root / "userdata/1234/config/localconfig.vdf"
local.parent.mkdir(parents=True)
local.write_text('"UserLocalConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n'
                 '\t\t\t\t"apps"\n\t\t\t\t{\n\t\t\t\t\t"%s"\n\t\t\t\t\t{\n\t\t\t\t\t\t"LaunchOptions"\t\t"-skipintro"\n'
                 '\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n' % APPID)
(root / "config").mkdir()
(root / "config/config.vdf").write_text('"InstallConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n'
                                       '\t\t\t"Steam"\n\t\t\t{\n\t\t\t\t"CompatToolMapping"\n\t\t\t\t{\n\t\t\t\t}\n'
                                       '\t\t\t}\n\t\t}\n\t}\n}\n')
# the shared knowledge, as sloth-windows-prepare downloads it: ProtonDB's setting for this game
kn = home / ".cache/sloth-os/knowledge.json"
kn.parent.mkdir(parents=True)
kn.write_text(json.dumps({"version": 1, "programs": {}, "games": {f"umu-{APPID}": {"any": {
    "line": "UMU-Proton", "profile": "wined3d", "fixes": [["env", "PROTON_NO_D3D11"]], "reports": 12}}}}))

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication([])
from sloth_common import sharing, steam_doctor  # noqa: E402
from sloth_center import games  # noqa: E402

print("== the game closes right after starting (what the game-mode service records)")
check("noted as failed", steam_doctor.record_run(APPID, 4) == "failed")
ctl = games.GamesController()
game = next((g for g in ctl._games if g["id"] == f"steam:{APPID}"), None)
check("Sloth Center lists the game", game is not None)
s = ctl._doctor(APPID, root)
check("its summary: a fix can be tried", s.get("canTry") is True, s)

print("== Try a fix (Steam not running)")
done = threading.Event()
ctl._fixed.connect(lambda gid, msg: (print("    message:", msg), done.set()))
ctl.tryFix(f"steam:{APPID}")
for _ in range(100):
    QCoreApplication.processEvents()
    if done.is_set():
        break
    time.sleep(0.1)
check("finished", done.is_set())
QCoreApplication.processEvents()
options, tool = steam_doctor.read_settings(root, local, APPID)
check("the shared setting went into the launch options, the user's words stay",
      options == "PROTON_USE_WINED3D=1 PROTON_NO_D3D11=1 %command% -skipintro", options)
check("Steam's own Windows runtime kept", tool is None, tool)
check("the game was started again", f"steam://rungameid/{APPID}" in (home / "calls").read_text())
check("the message names the fix", "on other computers" in ctl._info, ctl._info)

print("== the game runs 5 minutes; sharing for Steam games off, then on")
sharing.set_enabled(True)          # only the Windows programs' yes: not enough
check("worked", steam_doctor.record_run(APPID, 300) == "worked")
check("nothing queued without the games switch", not sharing.GAMES_QUEUE.exists() and not sharing.QUEUE.exists())
sharing.set_games_enabled(True)
steam_doctor.record_run(APPID, 3)   # it stopped working again: the failure is reported now, once
steam_doctor.record_run(APPID, 3)   # (a second quick close says nothing new)
queued = [json.loads(x) for x in sharing.GAMES_QUEUE.read_text().splitlines()]
check("one failure queued in the games queue", len(queued) == 1 and queued[0]["outcome"] == "failed", queued)
steam_doctor.try_next(root, local, APPID)    # the next fix (without fsync) ...
steam_doctor.record_run(APPID, 400)          # ... works: reported too
queued = [json.loads(x) for x in sharing.GAMES_QUEUE.read_text().splitlines()]
check("the next fix that worked queued too", [(q["profile"], q["outcome"]) for q in queued]
      == [("wined3d", "failed"), ("nofsync", "worked")], queued)

print("== sent to a local stand-in for the knowledge service")
got = []


class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        got.extend(json.loads(self.rfile.read(int(self.headers["content-length"]))))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
from sloth_exe import community  # noqa: E402
community.REPORT_URL = f"http://127.0.0.1:{srv.server_port}/v1/report"
check("sent", community.send_queue() == 2)
check("the games queue is empty afterwards", not sharing.GAMES_QUEUE.exists())
Path("/tmp/reports.json").write_text(json.dumps(got))

worker = Path("/repo/services/knowledge/src/worker.js").read_text()
head = worker[:worker.index("function validate")]
head = "\n".join(line for line in head.splitlines() if not line.startswith(("import", "export")))
fn = worker[worker.index("function validate"):]
fn = fn[:fn.index("\n}\n") + 3]
Path("/tmp/v.js").write_text(head + "\n" + fn + """
const reports = JSON.parse(require("fs").readFileSync("/tmp/reports.json", "utf8"));
for (const r of reports) console.log(JSON.stringify(validate(r)));
""")
out = subprocess.run(["node", "/tmp/v.js"], capture_output=True, text=True)
lines = [x for x in out.stdout.splitlines() if x.strip()]
print("    the service's validate():", *lines, out.stderr.strip()[:300], sep="\n      ")
check("the service accepts every report", len(lines) == 2 and "null" not in lines, out.stderr[:200])
check("the game is known by its Steam fingerprint",
      all(r["program"] == __import__("sloth_common.knowledge", fromlist=["x"]).steam_key(APPID) for r in got))
print(f"\n{ok} OK, {bad} ERROR")
sys.exit(1 if bad else 0)
