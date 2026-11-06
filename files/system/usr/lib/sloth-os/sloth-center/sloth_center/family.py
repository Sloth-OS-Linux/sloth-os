"""Parental controls: child accounts, their screen time and the apps they may open.

malcontent keeps the settings in AccountsService; an administrator reads them without a password (malcontent's own
polkit rule), and changes go through sloth-helper-family (pkexec). The screen time is enforced by
/usr/libexec/sloth-os/screen-time (system side) and shown in the child's session by family_session; Flatpak refuses to
start a blocked app by itself.

A child account is an ordinary account (not an administrator). An administrator is never limited.
Websites: /usr/libexec/sloth-os/family-web filters a child's name lookups (the list: /etc/sloth-os/family-web.json).
Windows programs and AppImages (sloth-exe): blocked by content type in the same malcontent app filter.
"""
import getpass
import grp
import json
import logging
import pwd
import re
import subprocess
import threading
import time
import unicodedata

from gi.repository import Gio, GLib
from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.family")

HELPER = "/usr/libexec/sloth-os/sloth-helper-family"
POLICY = "/etc/sloth-os/admin-policy.json"
FAMILY_WEB = "/etc/sloth-os/family-web.json"
# sloth-exe checks the first one; sloth-helper blocks all of them together (PROGRAM_TYPES)
PROGRAM_TYPE = "application/x-ms-dos-executable"
TIMER = ("org.freedesktop.MalcontentTimer1", "/org/freedesktop/MalcontentTimer1")
# the daily limit choices, in minutes (0: no limit)
DAILY_CHOICES = (0, 30, 60, 90, 120, 180, 240, 360)
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def _malcontent():
    import gi
    gi.require_version("Malcontent", "0")
    from gi.repository import Malcontent
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    return Malcontent, Malcontent.Manager.new(bus), bus


def _wheel():
    try:
        g = grp.getgrnam("wheel")
        return set(g.gr_mem), g.gr_gid
    except KeyError:
        return set(), -1


def child_accounts():
    """The ordinary accounts (not administrators, not system accounts), sorted by name."""
    members, gid = _wheel()
    out = []
    for pw in pwd.getpwall():
        if 1000 <= pw.pw_uid < 60000 and pw.pw_name not in members and pw.pw_gid != gid \
                and not pw.pw_shell.endswith(("nologin", "false")):
            out.append(pw)
    return sorted(out, key=lambda p: (p.pw_gecos.split(",")[0] or p.pw_name).casefold())


def installed_apps():
    """The apps installed for everyone (Flatpak): [{id, name, ref}]."""
    try:
        r = subprocess.run(["flatpak", "list", "--system", "--app", "--columns=application,name,ref"],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    apps = {}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2].startswith("app/"):
            apps.setdefault(parts[0], {"id": parts[0], "name": parts[1] or parts[0], "ref": parts[2]})
    return sorted(apps.values(), key=lambda a: a["name"].casefold())


def suggest_username(full_name):
    """"Kis Péter" -> "kispeter": what the account is called on the computer."""
    plain = unicodedata.normalize("NFKD", full_name)
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    name = re.sub(r"[^a-z0-9]", "", plain)[:32]
    return name if name and name[0].isalpha() else ""


def used_today(bus, uid):
    """Seconds of screen time today (malcontent-timerd; a parent may ask about their children)."""
    try:
        entries = bus.call_sync(TIMER[0], TIMER[1], "org.freedesktop.MalcontentTimer1.Parent", "QueryUsage",
                                GLib.Variant("(uss)", (uid, "login-session", "")), GLib.VariantType("(a(tt))"),
                                Gio.DBusCallFlags.NONE, 10000, None).unpack()[0]
    except GLib.Error as e:
        log.info("QueryUsage %s: %s", uid, e.message)
        return 0
    now = time.time()
    t = time.localtime(now)
    midnight = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))
    total = 0
    for start, end in entries:
        start, end = max(start, midnight), min(end + 1, now)  # end times are inclusive
        if end > start:
            total += end - start
    return int(total)


def own_time_left():
    """Seconds of screen time left for the account using Sloth Center, or -1 without a limit."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        now, times = bus.call_sync(TIMER[0], TIMER[1], "org.freedesktop.MalcontentTimer1.Child",
                                   "GetEstimatedTimes", GLib.Variant("(s)", ("login-session",)),
                                   GLib.VariantType("(ta{s(btttt)})"), Gio.DBusCallFlags.NONE, 10000, None).unpack()
    except GLib.Error:
        return -1
    entry = times.get("")
    if not entry:
        return -1
    return 0 if entry[0] else max(0, int(entry[2]) - int(now))


def web_filtered():
    """The accounts with the web filter on."""
    try:
        users = json.load(open(FAMILY_WEB, encoding="utf-8")).get("users", [])
    except (OSError, ValueError, AttributeError):
        return set()
    return {u for u in users if isinstance(u, str)} if isinstance(users, list) else set()


def autologin_user():
    try:
        users = json.load(open(POLICY, encoding="utf-8")).get("users", {})
    except (OSError, ValueError, AttributeError):
        return ""
    return next((u for u, cfg in users.items() if isinstance(cfg, dict) and cfg.get("autologin")), "")


def duration_text(secs):
    hours, minutes = divmod(int(secs) // 60, 60)
    if hours and minutes:
        return tr("{h} h {m} min", h=hours, m=minutes)
    if hours:
        return tr("{h} h", h=hours)
    return tr("{m} min", m=minutes)


class FamilyController(QObject):
    changed = Signal()
    childAdded = Signal()   # the form on the page is emptied
    _done = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user = getpass.getuser()
        self._admin = False
        self._children = []
        self._apps = []
        self._autologin = ""
        self._own_left = -1
        self._error = ""
        self._info = ""
        self._busy = False
        self._done.connect(self._on_done)
        self.refresh()

    isAdmin = Property(bool, lambda self: self._admin, notify=changed)
    children = Property("QVariantList", lambda self: list(self._children), notify=changed)
    apps = Property("QVariantList", lambda self: list(self._apps), notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    dailyChoices = Property("QVariantList", lambda self: list(DAILY_CHOICES), constant=True)

    @Property(str, notify=changed)
    def autologinWarning(self):
        if not self._autologin:
            return ""
        try:
            name = pwd.getpwnam(self._autologin).pw_gecos.split(",")[0] or self._autologin
        except KeyError:
            name = self._autologin
        return tr("Automatic sign-in is on: the computer starts into {name}'s account without a password, so a "
                  "child could use it. Turn it off in Account and security.", name=name)

    @Property(str, notify=changed)
    def ownTimeText(self):
        if self._own_left < 0:
            return ""
        return tr("Screen time left today: {time}", time=duration_text(self._own_left))

    @Slot(int, result=str)
    def durationText(self, minutes):
        return tr("No limit") if minutes <= 0 else duration_text(minutes * 60)

    @Slot(str, result=str)
    def suggestUsername(self, full_name):
        return suggest_username(full_name)

    @Slot()
    def refresh(self):
        members, _gid = _wheel()
        self._admin = self._user in members
        self._autologin = autologin_user()
        self._own_left = -1 if self._admin else own_time_left()
        self._children = []
        if self._admin:
            self._apps = installed_apps()
            self._children = self._read_children()
        self.changed.emit()

    def _read_children(self):
        try:
            Malcontent, manager, bus = _malcontent()
        except Exception as e:  # malcontent missing: the page says it can't read the settings
            log.warning("malcontent: %s", e)
            Malcontent = manager = bus = None
        signed_in = self._signed_in()
        filtered = web_filtered()
        out = []
        for pw in child_accounts():
            item = {"user": pw.pw_name, "name": pw.pw_gecos.split(",")[0] or pw.pw_name, "uid": pw.pw_uid,
                    "signedIn": pw.pw_uid in signed_in, "daily": 0, "scheduleOn": False, "start": 16, "end": 20,
                    "blocked": [], "programs": True, "web": pw.pw_name in filtered, "used": "",
                    "readable": manager is not None}
            if manager is not None:
                try:
                    limits = manager.get_session_limits(pw.pw_uid, Malcontent.ManagerGetValueFlags.NONE, None)
                    on, start, end = limits.get_daily_schedule()
                    item["scheduleOn"] = bool(on)
                    if on:
                        item["start"], item["end"] = start // 3600, (end + 3599) // 3600
                    on, daily = limits.get_daily_limit()
                    item["daily"] = daily // 60 if on else 0
                    app_filter = manager.get_app_filter(pw.pw_uid, Malcontent.ManagerGetValueFlags.NONE, None)
                    item["blocked"] = [a["id"] for a in self._apps if not app_filter.is_flatpak_app_allowed(a["id"])]
                    item["programs"] = bool(app_filter.is_content_type_allowed(PROGRAM_TYPE))
                    if item["daily"] or item["scheduleOn"]:
                        item["used"] = tr("Used today: {time}", time=duration_text(used_today(bus, pw.pw_uid)))
                except Exception as e:
                    log.warning("%s: %s", pw.pw_name, e)
                    item["readable"] = False
            out.append(item)
        return out

    @staticmethod
    def _signed_in():
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            users = bus.call_sync("org.freedesktop.login1", "/org/freedesktop/login1",
                                  "org.freedesktop.login1.Manager", "ListUsers", None, GLib.VariantType("(a(uso))"),
                                  Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
            return {u[0] for u in users}
        except GLib.Error:
            return set()

    # --- changes (through the helper, in the background: pkexec waits for the password) ----------------

    def _run(self, kind, args, request):
        if self._busy:
            return
        self._busy, self._error, self._info = True, "", ""
        self.changed.emit()

        def work():
            try:
                r = subprocess.run(["pkexec", HELPER, *args], input=json.dumps(request) if request is not None else "",
                                   capture_output=True, text=True, timeout=300)
                result = json.loads(r.stdout or "{}")
            except (OSError, subprocess.SubprocessError, ValueError) as e:
                log.warning("%s: %s", args[0], e)
                result = {}
            self._done.emit(kind, result)
        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, kind, result):
        self._busy = False
        if result.get("ok"):
            self._info = {"add": tr("The account is ready. The child can sign in with it on the sign-in screen."),
                          "remove": tr("The account has been deleted.")}.get(kind, tr("Saved."))
            if result.get("warning"):
                log.warning("%s: %s", kind, result["warning"])
        elif result.get("error") == "exists":
            self._error = tr("There's already an account with this username. Choose another one.")
        elif not result:
            self._error = tr("Couldn't change it. This needs administrator approval.")
        else:
            log.warning("%s: %s", kind, result.get("error"))
            self._error = tr("Couldn't change it. Try again, or restart the computer if it keeps happening.")
        self.refresh()
        if kind == "add" and result.get("ok"):
            self.childAdded.emit()

    @Slot(str, str, str, str)
    def addChild(self, full_name, username, password, password2):
        self._error, self._info = "", ""
        username = username.strip()
        if not full_name.strip() or not USER_RE.match(username):
            self._error = tr("Give a name, and a username of small letters and numbers (e.g. anna).")
        elif not password:
            self._error = tr("Give the child a password.")
        elif password != password2:
            self._error = tr("The two passwords don't match.")
        else:
            self._run("add", ["child-add"], {"username": username, "fullname": full_name.strip(),
                                             "password": password})
            return
        self.changed.emit()

    @Slot(str, int, bool, int, int)
    def setScreenTime(self, user, daily_minutes, schedule_on, start_hour, end_hour):
        if daily_minutes not in DAILY_CHOICES or not 0 <= start_hour < end_hour <= 24:
            self.refresh()  # the lists on the page go back to what is saved
            self._error = tr("The end of the allowed hours must be later than the start.")
            self.changed.emit()
            return
        request = {"daily": daily_minutes * 60, "start": None, "end": None}
        if schedule_on:
            request.update(start=start_hour * 3600, end=end_hour * 3600)
        self._run("limits", ["child-limits", user], request)

    @Slot(str, str, bool)
    def setAppAllowed(self, user, app_id, allowed):
        child = next((c for c in self._children if c["user"] == user), None)
        if child is None:
            return
        blocked = set(child["blocked"]) - {app_id} if allowed else set(child["blocked"]) | {app_id}
        refs = [a["ref"] for a in self._apps if a["id"] in blocked]
        self._run("apps", ["child-apps", user], {"blocked": refs, "programs": child["programs"]})

    @Slot(str, bool)
    def setProgramsAllowed(self, user, allowed):
        """Windows programs and AppImages (sloth-exe)."""
        child = next((c for c in self._children if c["user"] == user), None)
        if child is None:
            return
        refs = [a["ref"] for a in self._apps if a["id"] in set(child["blocked"])]
        self._run("apps", ["child-apps", user], {"blocked": refs, "programs": bool(allowed)})

    @Slot(str, bool)
    def setWebFilter(self, user, on):
        self._run("web", ["child-web", user, "on" if on else "off"], None)

    @Slot(str)
    def removeChild(self, user):
        self._run("remove", ["child-remove", user], None)
