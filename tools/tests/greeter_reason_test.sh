#!/usr/bin/bash
# Run (screenshots into ./shots): podman run --rm -v "$PWD":/repo:ro -v "$PWD/shots":/out -e OUT=/out ghcr.io/sloth-os-linux/sloth-os:<tag> bash /repo/tools/tests/greeter_reason_test.sh
# Visual test of the rebuilt sign-in screen (files/scripts/greeter-reason.sh), in the Sloth OS image:
# the same source package and the same Main.qml change, plus (only here) a test mock that answers like the real
# daemon does: a refused child = our marked reason, then PAM's "System error", then loginFailed; a wrong password =
# "Authentication failure", then loginFailed. The greeter's --test mode signs in by itself and saves screenshots.
set -euo pipefail
OUT=${OUT:-/tmp/greeter-shots}
WORK=/tmp/gv
nvr=$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' plasma-login-manager)
mkdir -p "$WORK" && cd "$WORK"
dnf -y -q install --setopt=install_weak_deps=False rpm-build dnf5-plugins >/dev/null
dnf -y -q download --srpm --enablerepo=fedora-source --enablerepo=updates-source --destdir="$WORK" "$nvr" >/dev/null
top="$WORK/rpmbuild"
rpm -i --define "_topdir $top" "$WORK/$nvr.src.rpm" 2>/dev/null
spec=$(ls "$top"/SPECS/*.spec)
dnf -y -q builddep --setopt=install_weak_deps=False "$spec" >/dev/null
rpmbuild --define "_topdir $top" -bp --nodeps "$spec" >/dev/null 2>&1
src=$(dirname "$(dirname "$(dirname "$(dirname "$(find "$top/BUILD" -path '*/src/frontend/greeter/qml/Main.qml' | head -n1)")")")")
echo "source: $src"

# 1. the real change, exactly as the image build makes it
awk "/<<'PYEOF'/{f=1;next}/^PYEOF/{f=0}f" /repo/files/scripts/greeter-reason.sh > /tmp/patch.py
python3 /tmp/patch.py "$src/frontend/greeter/qml/Main.qml"
grep -c slothReason "$src/frontend/greeter/qml/Main.qml"

# 2. test only: the mock answers like the daemon, and --test signs in by itself and takes screenshots
python3 - "$src" <<'EOF'
import sys
from pathlib import Path
src = Path(sys.argv[1])
mock = src / "frontend/greeter/mockbackend/MockGreeterProxy.cpp"
s = mock.read_text()
old = "    } else {\n        QTimer::singleShot(100, this, &MockGreeterProxy::loginFailed);\n    }"
assert s.count(old) == 1
s = s.replace(old, """    } else if (password == QStringLiteral("child")) {
        // as the daemon does for a child refused by the screen time check (pam_exec's text, then PAM's error)
        QTimer::singleShot(50, this, [this]() {
            Q_EMIT const_cast<MockGreeterProxy *>(this)->informationMessage(QString(QChar(0x2063)) + QStringLiteral("Your allowed hours haven't started yet. You can use the computer from 16:00."));
            Q_EMIT const_cast<MockGreeterProxy *>(this)->informationMessage(QStringLiteral("System error"));
            Q_EMIT const_cast<MockGreeterProxy *>(this)->loginFailed();
        });
    } else {
        QTimer::singleShot(50, this, [this]() {
            Q_EMIT const_cast<MockGreeterProxy *>(this)->informationMessage(QStringLiteral("Authentication failure"));
            Q_EMIT const_cast<MockGreeterProxy *>(this)->loginFailed();
        });
    }""")
mock.write_text(s)
main = src / "frontend/greeter/main.cpp"
s = main.read_text()
s = s.replace("#include \"mockbackend/MockGreeterProxy.h\"",
              "#include \"mockbackend/MockGreeterProxy.h\"\n#include <QMouseEvent>\n#include <QQuickItem>\n#include <QTimer>\n", 1)
old = "    LoginGreeter greeter;\n    return app.exec();"
assert s.count(old) == 1
s = s.replace(old, r'''    LoginGreeter greeter;
    if (LoginGreeter::testModeEnabled() && qEnvironmentVariableIsSet("SLOTH_SHOTS")) {
        auto view = []() -> QQuickView * {
            for (QWindow *w : QGuiApplication::topLevelWindows())
                if (auto *v = qobject_cast<QQuickView *>(w))
                    return v;
            return nullptr;
        };
        auto shoot = [view](const QString &name) {
            if (auto *v = view()) {
                static int n = 0; QPoint p(10 + (n++ % 2) * 7, 10);   // a real movement keeps the sign-in part visible
                QMouseEvent move(QEvent::MouseMove, p, v->mapToGlobal(p), Qt::NoButton, Qt::NoButton, Qt::NoModifier);
                QGuiApplication::sendEvent(v, &move);
                v->grabWindow().save(QString::fromLocal8Bit(qgetenv("SLOTH_SHOTS")) + QStringLiteral("/") + name + QStringLiteral(".png"));
                qWarning() << "shot" << name;
            }
        };
        auto login = [view](const QString &pw) {
            if (auto *v = view()) {
                QMetaObject::invokeMethod(v->rootObject(), "handleLoginRequest",
                                          Q_ARG(QVariant, QVariant(QStringLiteral("anna"))), Q_ARG(QVariant, QVariant(pw)));
                qWarning() << "login" << pw;
            }
        };
        QTimer::singleShot(2500, [=]() { shoot(QStringLiteral("0-start")); });
        QTimer::singleShot(3000, [=]() { login(QStringLiteral("child")); });
        QTimer::singleShot(4500, [=]() { shoot(QStringLiteral("1-child-refused")); });
        QTimer::singleShot(8000, [=]() { shoot(QStringLiteral("2-child-still-after-4s")); });
        QTimer::singleShot(8200, [=]() { login(QStringLiteral("wrong")); });
        QTimer::singleShot(9600, [=]() { shoot(QStringLiteral("3-wrong-password")); });
        QTimer::singleShot(12500, [=]() { shoot(QStringLiteral("4-wrong-cleared-after-3s")); });
        QTimer::singleShot(12800, [=]() { login(QStringLiteral("child")); });
        QTimer::singleShot(14300, [=]() { shoot(QStringLiteral("5-child-again")); QCoreApplication::quit(); });
    }
    return app.exec();''')
main.write_text(s)
print("test patches in")
EOF

rpmbuild --define "_topdir $top" -bf --short-circuit --nodeps "$spec" >/tmp/conf.log 2>&1 || { tail -20 /tmp/conf.log; exit 1; }
rpmbuild --define "_topdir $top" -bc --short-circuit --nocheck --nodeps "$spec" >/tmp/build.log 2>&1 || { grep -B2 -A8 "error" /tmp/build.log | head -40; exit 1; }
built=$(find "$top/BUILD" -type f -name plasma-login-greeter -perm -u+x | head -n1)
echo "built: $built"
mkdir -p /tmp/rt && chmod 700 /tmp/rt
mkdir -p "$OUT"
SLOTH_SHOTS="$OUT" XDG_RUNTIME_DIR=/tmp/rt QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
    QT_QPA_OFFSCREEN_NO_GLX=1 timeout 40 "$built" --test 2>&1 | grep -vE "^\s*$" | grep -iE "shot|login|qml|error|warning" | head -30 || true
ls -la "$OUT"
