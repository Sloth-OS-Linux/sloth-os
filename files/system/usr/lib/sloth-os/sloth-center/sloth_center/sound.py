"""Sound before gaming (Drivers and hardware page): where the sound goes, which microphone is used, and trying both.

The devices come from PipeWire through pactl (its JSON "description" can be "(null)", so the name is taken from
the properties: the node's nick names an HDMI output after the monitor, e.g. "U34G3XM"). Choosing one makes it
the default (pactl set-default-sink / -source; WirePlumber moves the running sound over). The microphone test
records four seconds, says whether it heard anything at all, and plays it back.
"""
import array
import json
import logging
import os
import signal
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.sound")

TEST_SOUND = "/usr/share/sounds/freedesktop/stereo/audio-test-signal.oga"
RECORD_SECONDS = 4
QUIET = 600  # the loudest sample below this (of 32767) means nothing was heard


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("%s: %s", cmd[0], e)
        return ""


def _label(device):
    """A readable name: the description, otherwise the node's or the device's nick from the properties."""
    props = device.get("properties") or {}
    for value in (device.get("description"), props.get("node.description"), props.get("node.nick"),
                  props.get("device.description"), props.get("device.nick")):
        if value and value != "(null)":
            return value
    return device.get("name", "")


def devices(kind, run=_run):
    """kind "sinks" (speakers, headphones) or "sources" (microphones; the monitors of outputs are left out):
    [{name, label, muted}]."""
    try:
        items = json.loads(run(["pactl", "-f", "json", "list", kind]) or "[]")
    except ValueError:
        return []
    result = []
    for d in items:
        name = d.get("name", "")
        if not name or name.endswith(".monitor"):
            continue
        result.append({"name": name, "label": _label(d), "muted": bool(d.get("mute"))})
    return result


def default(kind, run=_run):
    return run(["pactl", "get-default-sink" if kind == "sinks" else "get-default-source"]).strip()


def peak(path):
    """The loudest sample of a 16-bit WAV file (0 if it cannot be read)."""
    try:
        with wave.open(str(path), "rb") as w:
            if w.getsampwidth() != 2:
                return 0
            samples = array.array("h", w.readframes(w.getnframes()))
    except (OSError, EOFError, wave.Error):
        return 0
    return max((abs(s) for s in samples), default=0)


class SoundController(QObject):
    changed = Signal()
    _micDone = Signal(str, str)  # state, text (from the recording thread)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._outputs, self._inputs = [], []
        self._output = self._input = ""
        self._mic_state = ""   # "", "recording", "playing", "ok", "quiet", "failed"
        self._mic_text = ""
        self._micDone.connect(self._on_mic)
        # the devices are read when the Drivers and hardware page opens (not at every start of Sloth Center)

    outputs = Property("QVariantList", lambda self: list(self._outputs), notify=changed)
    inputs = Property("QVariantList", lambda self: list(self._inputs), notify=changed)
    currentOutput = Property(str, lambda self: self._output, notify=changed)
    currentInput = Property(str, lambda self: self._input, notify=changed)
    micState = Property(str, lambda self: self._mic_state, notify=changed)
    micText = Property(str, lambda self: self._mic_text, notify=changed)

    @Property(bool, notify=changed)
    def inputMuted(self):
        return any(i["name"] == self._input and i["muted"] for i in self._inputs)

    @Slot()
    def refresh(self):
        self._outputs, self._inputs = devices("sinks"), devices("sources")
        self._output, self._input = default("sinks"), default("sources")
        self.changed.emit()

    @Slot(str)
    def setOutput(self, name):
        _run(["pactl", "set-default-sink", name])
        self.refresh()

    @Slot(str)
    def setInput(self, name):
        _run(["pactl", "set-default-source", name])
        self._mic_state = self._mic_text = ""
        self.refresh()

    @Slot()
    def unmuteInput(self):
        _run(["pactl", "set-source-mute", self._input or "@DEFAULT_SOURCE@", "0"])
        self.refresh()

    @Slot()
    def playTest(self):
        try:
            subprocess.Popen(["pw-play", TEST_SOUND], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("pw-play: %s", e)

    @Slot()
    def testMic(self):
        if self._mic_state in ("recording", "playing"):
            return
        self._mic_state, self._mic_text = "recording", tr("Say something now…")
        self.changed.emit()
        threading.Thread(target=self._record_and_play, daemon=True).start()

    def _record_and_play(self):
        fd, path = tempfile.mkstemp(prefix="sloth-mic-", suffix=".wav")
        os.close(fd)
        try:
            rec = subprocess.Popen(["pw-record", "--rate", "48000", "--channels", "1", "--format", "s16", path],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(RECORD_SECONDS)
            rec.send_signal(signal.SIGINT)  # pw-record finishes the file on SIGINT
            rec.wait(timeout=5)
            loudest = peak(path)
            if not loudest and not Path(path).stat().st_size:
                self._micDone.emit("failed", tr("Couldn't record from the microphone."))
                return
            self._micDone.emit("playing", tr("Playing it back…"))
            subprocess.run(["pw-play", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=RECORD_SECONDS + 10)
            if loudest < QUIET:
                self._micDone.emit("quiet", tr("It heard nothing. Check that this is the right microphone, that it is plugged in, and that it isn't muted."))
            else:
                self._micDone.emit("ok", tr("It heard you. If the playback sounded right, the microphone works."))
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("microphone test: %s", e)
            self._micDone.emit("failed", tr("Couldn't record from the microphone."))
        finally:
            Path(path).unlink(missing_ok=True)

    def _on_mic(self, state, text):
        self._mic_state, self._mic_text = state, text
        self.changed.emit()
