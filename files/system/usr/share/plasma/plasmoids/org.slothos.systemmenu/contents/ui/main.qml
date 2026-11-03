/*
    Sloth OS system menu, for the macOS-like layout: the logo at the left of the top bar opens a small menu, as the
    Apple menu does: About This Computer (Info Center), System Settings (Sloth Center), the App Store (Discover),
    Force Quit (KWin's kill window), Sleep, Restart, Shut Down, Lock Screen, Log Out. The apps start from the
    Launchpad in the dock. Texts: strings.js (Sloth OS's 50 languages).

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.plasmoid
import org.kde.plasma.private.sessions as Sessions

import "strings.js" as Strings

PlasmoidItem {
    id: root

    function t(key) {
        return Strings.tr(Qt.locale().name, key);
    }

    function run(command) {
        executable.connectSource(command);
    }

    Plasmoid.icon: "sloth-os"
    toolTipMainText: ""
    toolTipSubText: ""
    preferredRepresentation: fullRepresentation
    switchWidth: 0
    switchHeight: 0

    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => disconnectSource(source)
    }

    Sessions.SessionManagement {
        id: session
    }

    fullRepresentation: MouseArea {
        id: button

        Layout.minimumWidth: Kirigami.Units.iconSizes.small
        Layout.maximumWidth: Kirigami.Units.iconSizes.medium
        Layout.minimumHeight: Kirigami.Units.iconSizes.small
        hoverEnabled: true
        Accessible.role: Accessible.ButtonMenu
        Accessible.name: Plasmoid.title
        onClicked: menu.openRelative()

        Kirigami.Icon {
            anchors.fill: parent
            source: Plasmoid.icon
            active: button.containsMouse || menu.status === PlasmaExtras.Menu.Open
            roundToIconSize: true
        }

        Connections {
            target: Plasmoid
            function onActivated() {
                menu.openRelative();
            }
        }

        PlasmaExtras.Menu {
            id: menu
            visualParent: button
            placement: PlasmaExtras.Menu.BottomPosedLeftAlignedPopup

            PlasmaExtras.MenuItem {
                text: root.t("about")
                icon: "help-about"
                onClicked: root.run("kinfocenter")
            }
            PlasmaExtras.MenuItem { separator: true }
            PlasmaExtras.MenuItem {
                text: root.t("settings")
                icon: "preferences-system"
                onClicked: root.run("sloth-center")
            }
            PlasmaExtras.MenuItem {
                text: root.t("store")
                icon: "plasmadiscover"
                onClicked: root.run("plasma-discover")
            }
            PlasmaExtras.MenuItem { separator: true }
            PlasmaExtras.MenuItem {
                text: root.t("forcequit")
                icon: "process-stop"
                // KWin's own "kill a window": the next click closes that window for good
                onClicked: root.run("dbus-send --session --type=method_call --dest=org.kde.KWin /KWin org.kde.KWin.killWindow")
            }
            PlasmaExtras.MenuItem { separator: true }
            PlasmaExtras.MenuItem {
                text: root.t("sleep")
                icon: "system-suspend"
                visible: session.canSuspend
                onClicked: session.suspend()
            }
            PlasmaExtras.MenuItem {
                text: root.t("restart")
                icon: "system-reboot"
                visible: session.canReboot
                onClicked: session.requestReboot()
            }
            PlasmaExtras.MenuItem {
                text: root.t("shutdown")
                icon: "system-shutdown"
                visible: session.canShutdown
                onClicked: session.requestShutdown()
            }
            PlasmaExtras.MenuItem { separator: true }
            PlasmaExtras.MenuItem {
                text: root.t("lock")
                icon: "system-lock-screen"
                visible: session.canLock
                onClicked: session.lock()
            }
            PlasmaExtras.MenuItem {
                text: root.t("logout")
                icon: "system-log-out"
                visible: session.canLogout
                onClicked: session.requestLogout()
            }
        }
    }
}
