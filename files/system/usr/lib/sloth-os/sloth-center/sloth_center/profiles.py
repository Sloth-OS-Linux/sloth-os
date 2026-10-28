"""Display and sound profiles (Drivers and hardware page): "Desk", "TV", "Headset" saved and switched with one click.

A profile is the state of the monitors (on or off, resolution and refresh rate, position, scale, which is the main
one) and the default speakers / headphones and microphone. It is saved from the current setup and applied with
kscreen-doctor and pactl. Only the monitors connected now are changed: a profile's monitor that is not plugged in is
left out, and a profile that would turn every monitor off is not applied. The mode is found again by its size and
refresh rate (the mode ids of kscreen can change). Applying goes through the Displays card's "Keep this setting?"
question (display.py), which also puts the sound back if the user goes back.
"""
import json
import os
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os" / "profiles.json"


def load(path=None):
    try:
        data = json.loads(Path(path or CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [p for p in data if isinstance(p, dict) and p.get("name")] if isinstance(data, list) else []


def save(profiles, path=None):
    path = Path(path or CONFIG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _mode(output, mode_id):
    return next((m for m in output.get("modes", []) if str(m.get("id")) == str(mode_id)), None)


def capture(name, screens, sink="", source=""):
    """The current setup as a profile. screens: kscreen-doctor -j's data."""
    displays = []
    for o in screens.get("outputs", []):
        if not o.get("connected"):
            continue
        entry = {"connector": o.get("name", ""), "enabled": bool(o.get("enabled"))}
        mode = _mode(o, o.get("currentModeId"))
        if o.get("enabled") and mode:
            size = mode.get("size") or {}
            entry.update(width=size.get("width", 0), height=size.get("height", 0),
                         refresh=round(mode.get("refreshRate", 0), 2),
                         x=(o.get("pos") or {}).get("x", 0), y=(o.get("pos") or {}).get("y", 0),
                         scale=o.get("scale", 1), priority=o.get("priority", 0))
        displays.append(entry)
    return {"name": name.strip(), "displays": displays, "sink": sink, "source": source}


def _find_mode(output, width, height, refresh):
    """The mode with this size and the closest refresh rate (not above it by more than half a hertz)."""
    same = [m for m in output.get("modes", [])
            if (m.get("size") or {}).get("width") == width and (m.get("size") or {}).get("height") == height]
    fitting = [m for m in same if m.get("refreshRate", 0) <= refresh + 0.5]
    pool = fitting or same
    return min(pool, key=lambda m: abs(m.get("refreshRate", 0) - refresh)) if pool else None


def _scale_text(value):
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text or "1"


def display_args(profile, screens):
    """kscreen-doctor arguments that make the connected monitors as in the profile, and the profile's monitors that
    are not connected now. -> (args, missing). args is [] if nothing would stay turned on."""
    connected = {o.get("name"): o for o in screens.get("outputs", []) if o.get("connected")}
    wanted = {d.get("connector"): d for d in profile.get("displays", [])}
    missing = [c for c in wanted if c not in connected]
    if not any(d.get("enabled") and c in connected for c, d in wanted.items()):
        return [], missing
    args = []
    # turned on first, then the others off: there is always a screen showing something
    for connector, d in wanted.items():
        output = connected.get(connector)
        if output is None or not d.get("enabled"):
            continue
        args.append(f"output.{connector}.enable")
        mode = _find_mode(output, d.get("width"), d.get("height"), d.get("refresh", 0))
        if mode:
            args.append(f"output.{connector}.mode.{mode.get('id')}")
        args.append(f"output.{connector}.position.{int(d.get('x', 0))},{int(d.get('y', 0))}")
        args.append(f"output.{connector}.scale.{_scale_text(d.get('scale', 1))}")
        if d.get("priority"):
            args.append(f"output.{connector}.priority.{int(d['priority'])}")
    for connector, d in wanted.items():
        if connector in connected and not d.get("enabled"):
            args.append(f"output.{connector}.disable")
    return args, missing


# --- Sloth Center ----------------------------------------------------------------------------------------------

from PySide6.QtCore import QObject, Property, Signal, Slot  # noqa: E402

from . import display as screens_info, sound  # noqa: E402
from .i18n import tr  # noqa: E402


class ProfilesController(QObject):
    """The profiles card; applying goes through the Displays card's controller (its "Keep this setting?")."""
    changed = Signal()

    def __init__(self, displays, parent=None):
        super().__init__(parent)
        self._displays = displays
        self._profiles = load()
        self._error = ""
        self._info = ""

    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)

    @Property("QVariantList", notify=changed)
    def profiles(self):
        sinks = {d["name"]: d["label"] for d in sound.devices("sinks")} if self._profiles else {}
        out = []
        for p in self._profiles:
            on = [screens_info._monitor_name(d["connector"]) for d in p.get("displays", []) if d.get("enabled")]
            parts = [", ".join(on)] if on else []
            if p.get("sink") in sinks:
                parts.append(sinks[p["sink"]])
            out.append({"name": p["name"], "summary": " · ".join(parts)})
        return out

    @Slot(str)
    def saveCurrent(self, name):
        name = name.strip()
        if not name:
            return
        profile = capture(name, self._displays.screens(), sound.default("sinks"), sound.default("sources"))
        self._profiles = [p for p in self._profiles if p["name"] != name] + [profile]
        save(self._profiles)
        self._error, self._info = "", tr("Saved: {name}", name=name)
        self.changed.emit()

    @Slot(str)
    def remove(self, name):
        self._profiles = [p for p in self._profiles if p["name"] != name]
        save(self._profiles)
        self._error = self._info = ""
        self.changed.emit()

    @Slot(str)
    def apply(self, name):
        profile = next((p for p in self._profiles if p["name"] == name), None)
        if not profile:
            return
        self._error = self._info = ""
        now = self._displays.screens()
        args, missing = display_args(profile, now)
        if not args:
            self._error = tr("None of this profile's screens is connected now.")
            self.changed.emit()
            return
        if missing:
            self._info = tr("Not connected now, so left out: {names}",
                            names=", ".join(screens_info._monitor_name(c) for c in missing))
        # the way back: the current setup, screens and sound
        before = capture("", now, sound.default("sinks"), sound.default("sources"))
        undo, _ = display_args(before, now)
        sinks = {d["name"] for d in sound.devices("sinks")}
        sources = {d["name"] for d in sound.devices("sources")}
        if profile.get("sink") in sinks:
            sound._run(["pactl", "set-default-sink", profile["sink"]])
        if profile.get("source") in sources:
            sound._run(["pactl", "set-default-source", profile["source"]])

        def sound_back():
            if before["sink"]:
                sound._run(["pactl", "set-default-sink", before["sink"]])
            if before["source"]:
                sound._run(["pactl", "set-default-source", before["source"]])
        self._displays._apply(args, undo, sound_back)
        self.changed.emit()
