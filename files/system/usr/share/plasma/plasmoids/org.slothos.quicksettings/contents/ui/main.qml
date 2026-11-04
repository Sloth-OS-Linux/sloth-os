/*
    Sloth OS quick settings, for the ChromeOS-like layout: in the shelf's corner a pill with the network, Bluetooth
    (if the computer has it), the sound and the clock; a click opens a bubble with the date, toggles (Wi-Fi, Bluetooth, do not disturb, airplane mode,
    power saver), the volume and the screen brightness, and Settings (Sloth Center), Screenshot, Lock and Shut down. It is built on the same parts as KDE's own network, sound,
    Bluetooth and brightness widgets. Texts: strings.js (Sloth OS's 50 languages).

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

import org.kde.bluezqt as BluezQt
import org.kde.kirigami as Kirigami
import org.kde.notificationmanager as NotificationManager
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.networkmanagement as PlasmaNM
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.plasmoid
import org.kde.plasma.private.batterymonitor as Battery
import org.kde.plasma.private.brightnesscontrolplugin as Brightness
import org.kde.plasma.private.sessions as Sessions
import org.kde.plasma.private.volume as Volume

import "strings.js" as Strings

PlasmoidItem {
    id: root

    readonly property var sink: Volume.PreferredDevice.sink
    readonly property int volumePercent: sink ? Math.round(sink.volume / Volume.PulseAudio.NormalVolume * 100) : 0
    readonly property string volumeIcon: !sink || sink.muted || volumePercent === 0 ? "audio-volume-muted"
        : volumePercent < 34 ? "audio-volume-low" : volumePercent < 67 ? "audio-volume-medium" : "audio-volume-high"
    property date now: new Date()

    function t(key) {
        return Strings.tr(Qt.locale().name, key);
    }

    function run(command) {
        executable.connectSource(command);
    }

    Plasmoid.icon: "preferences-system"
    toolTipMainText: Qt.formatDate(now, Qt.locale().dateFormat(Locale.LongFormat))
    toolTipSubText: ""
    preferredRepresentation: compactRepresentation

    Timer {
        interval: 10000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.now = new Date()
    }

    // the tray's network, sound… icons go behind its arrow (they are here): also on desktops set up before, a moment
    // after start, when the tray is up (/usr/libexec/sloth-os/quicksettings-tray; it does nothing twice)
    Timer {
        interval: 3000
        running: true
        onTriggered: root.run("/usr/libexec/sloth-os/quicksettings-tray")
    }

    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => disconnectSource(source)
    }

    PlasmaNM.ConnectionIcon {
        id: connectionIcon
    }

    PlasmaNM.EnabledConnections {
        id: enabledConnections
    }

    PlasmaNM.Handler {
        id: networkHandler
    }

    Brightness.ScreenBrightnessControl {
        id: brightnessControl
        isSilent: false
    }

    Sessions.SessionManagement {
        id: session
    }

    // do not disturb: notifications are held back until it is turned off, as in KDE's notification widget
    NotificationManager.Settings {
        id: notificationSettings
        live: true
    }
    readonly property bool doNotDisturb: {
        const until = notificationSettings.notificationsInhibitedUntil;
        return !isNaN(until) && until > now;
    }
    function setDoNotDisturb(on) {
        if (on) {
            const until = new Date();
            until.setFullYear(until.getFullYear() + 1);
            notificationSettings.notificationsInhibitedUntil = until;
        } else {
            notificationSettings.notificationsInhibitedUntil = undefined;
            notificationSettings.revokeApplicationInhibitions();
        }
        notificationSettings.save();
    }

    // power saver: the power profile, if the computer has them
    Battery.PowerProfilesControl {
        id: powerProfiles
    }
    readonly property bool canSavePower: powerProfiles.isPowerProfileDaemonInstalled
        && powerProfiles.profiles.indexOf("power-saver") >= 0

    // airplane mode: no radio at all (Wi-Fi and Bluetooth off)
    readonly property bool airplaneMode: !enabledConnections.wirelessEnabled && !enabledConnections.wwanEnabled
        && (BluezQt.Manager.adapters.length === 0 || BluezQt.Manager.bluetoothBlocked)

    // the pill in the shelf: network, sound, clock
    compactRepresentation: MouseArea {
        id: pill

        readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical

        Layout.minimumWidth: vertical ? -1 : pillRow.implicitWidth + Kirigami.Units.largeSpacing * 2
        Layout.preferredWidth: Layout.minimumWidth
        hoverEnabled: true
        property bool wasExpanded: false
        onPressed: wasExpanded = root.expanded
        onClicked: root.expanded = !wasExpanded

        Rectangle {
            anchors.fill: parent
            anchors.topMargin: Kirigami.Units.smallSpacing
            anchors.bottomMargin: Kirigami.Units.smallSpacing
            radius: height / 2
            color: Kirigami.Theme.textColor
            opacity: pill.containsMouse || root.expanded ? 0.16 : 0.08
        }

        RowLayout {
            id: pillRow
            anchors.centerIn: parent
            spacing: Kirigami.Units.smallSpacing

            Kirigami.Icon {
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
                Layout.preferredHeight: Kirigami.Units.iconSizes.small
                source: connectionIcon.connectionIcon
            }
            // Bluetooth only on a computer that has it (on or off at a glance)
            Kirigami.Icon {
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
                Layout.preferredHeight: Kirigami.Units.iconSizes.small
                visible: BluezQt.Manager.adapters.length > 0
                source: BluezQt.Manager.bluetoothBlocked ? "network-bluetooth-inactive" : "network-bluetooth"
            }
            Kirigami.Icon {
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
                Layout.preferredHeight: Kirigami.Units.iconSizes.small
                source: root.volumeIcon
            }
            PlasmaComponents.Label {
                Layout.leftMargin: Kirigami.Units.smallSpacing
                text: Qt.formatTime(root.now, Qt.locale().timeFormat(Locale.ShortFormat))
            }
        }
    }

    // a round toggle with its name below (Wi-Fi, Bluetooth)
    // every toggle as wide as the others, so the grid's columns line up (a long name wraps to a second line)
    readonly property int toggleWidth: Kirigami.Units.gridUnit * 5

    component Toggle: ColumnLayout {
        id: toggle

        required property string label
        required property string iconName
        required property bool checked
        signal toggled()

        Layout.preferredWidth: root.toggleWidth
        Layout.maximumWidth: root.toggleWidth
        Layout.alignment: Qt.AlignTop
        spacing: Kirigami.Units.smallSpacing

        PlasmaComponents.ToolButton {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Kirigami.Units.gridUnit * 3
            Layout.preferredHeight: Kirigami.Units.gridUnit * 3
            icon.name: toggle.iconName
            icon.width: Kirigami.Units.iconSizes.smallMedium
            icon.height: Kirigami.Units.iconSizes.smallMedium
            // on the highlight color the icon takes its text color (on a light highlight a light icon vanished)
            icon.color: toggle.checked ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
            checkable: true
            checked: toggle.checked
            onClicked: toggle.toggled()
            Accessible.name: toggle.label
            background: Rectangle {
                radius: width / 2
                color: toggle.checked ? Kirigami.Theme.highlightColor : Qt.alpha(Kirigami.Theme.textColor, 0.12)
            }
        }
        PlasmaComponents.Label {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: toggle.label
            font: Kirigami.Theme.smallFont
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
    }

    // the bubble
    fullRepresentation: ColumnLayout {
        // room for four toggles in a row
        Layout.preferredWidth: root.toggleWidth * 4 + Kirigami.Units.largeSpacing * 5
        Layout.minimumWidth: Layout.preferredWidth
        spacing: Kirigami.Units.largeSpacing

        Kirigami.Heading {
            Layout.fillWidth: true
            level: 4
            text: Qt.formatDate(root.now, Qt.locale().dateFormat(Locale.LongFormat))
        }

        GridLayout {
            Layout.alignment: Qt.AlignHCenter
            columns: 4
            columnSpacing: Kirigami.Units.largeSpacing
            rowSpacing: Kirigami.Units.largeSpacing

            Toggle {
                visible: enabledConnections.wirelessHwEnabled
                label: root.t("wifi")
                iconName: enabledConnections.wirelessEnabled ? "network-wireless-on" : "network-wireless-off"
                checked: enabledConnections.wirelessEnabled
                onToggled: networkHandler.enableWireless(!enabledConnections.wirelessEnabled)
            }
            Toggle {
                visible: BluezQt.Manager.adapters.length > 0
                label: root.t("bluetooth")
                iconName: BluezQt.Manager.bluetoothBlocked ? "network-bluetooth-inactive" : "network-bluetooth"
                checked: !BluezQt.Manager.bluetoothBlocked
                onToggled: BluezQt.Manager.bluetoothBlocked = !BluezQt.Manager.bluetoothBlocked
            }
            Toggle {
                label: root.t("dnd")
                iconName: root.doNotDisturb ? "notifications-disabled" : "notifications"
                checked: root.doNotDisturb
                onToggled: root.setDoNotDisturb(!root.doNotDisturb)
            }
            Toggle {
                visible: enabledConnections.wirelessHwEnabled || BluezQt.Manager.adapters.length > 0
                label: root.t("airplane")
                iconName: "network-flightmode-on"
                checked: root.airplaneMode
                onToggled: networkHandler.enableAirplaneMode(!root.airplaneMode)
            }
            Toggle {
                visible: root.canSavePower
                label: root.t("powersave")
                iconName: "battery-profile-powersave"
                checked: powerProfiles.activeProfile === "power-saver"
                onToggled: powerProfiles.setProfile(checked ? "balanced" : "power-saver")
            }
        }

        // the volume: the icon mutes
        RowLayout {
            Layout.fillWidth: true
            visible: root.sink !== null
            PlasmaComponents.ToolButton {
                icon.name: root.volumeIcon
                checkable: true
                checked: root.sink ? root.sink.muted : false
                onClicked: root.sink.muted = !root.sink.muted
                Accessible.name: root.t("volume")
                PlasmaComponents.ToolTip.text: root.t("volume")
                PlasmaComponents.ToolTip.visible: hovered
            }
            PlasmaComponents.Slider {
                Layout.fillWidth: true
                from: 0
                to: Volume.PulseAudio.NormalVolume
                stepSize: Volume.PulseAudio.NormalVolume / 100
                value: root.sink ? root.sink.volume : 0
                onMoved: {
                    root.sink.volume = value;
                    root.sink.muted = value === 0;
                }
                Accessible.name: root.t("volume")
            }
        }

        // the screen brightness, one slider for each screen that can be dimmed
        Repeater {
            model: brightnessControl.isBrightnessAvailable ? brightnessControl.displays : null

            delegate: RowLayout {
                id: brightnessRow

                required property string displayName
                required property int brightness
                required property int maxBrightness

                Layout.fillWidth: true
                Kirigami.Icon {
                    Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                    Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                    Layout.leftMargin: Kirigami.Units.smallSpacing
                    Layout.rightMargin: Kirigami.Units.smallSpacing
                    source: "brightness-high"
                }
                PlasmaComponents.Slider {
                    Layout.fillWidth: true
                    from: 0
                    to: brightnessRow.maxBrightness
                    stepSize: Math.max(1, brightnessRow.maxBrightness / 100)
                    value: brightnessRow.brightness
                    onMoved: brightnessControl.setBrightness(brightnessRow.displayName, value)
                    Accessible.name: root.t("brightness")
                }
            }
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            PlasmaComponents.ToolButton {
                icon.name: "configure"
                text: root.t("settings")
                onClicked: {
                    root.run("sloth-center");
                    root.expanded = false;
                }
            }
            Item { Layout.fillWidth: true }
            PlasmaComponents.ToolButton {
                icon.name: "spectacle"
                onClicked: {
                    root.expanded = false;
                    root.run("spectacle");
                }
                Accessible.name: root.t("screenshot")
                PlasmaComponents.ToolTip.text: root.t("screenshot")
                PlasmaComponents.ToolTip.visible: hovered
            }
            PlasmaComponents.ToolButton {
                visible: session.canLock
                icon.name: "system-lock-screen"
                onClicked: {
                    root.expanded = false;
                    session.lock();
                }
                Accessible.name: root.t("lock")
                PlasmaComponents.ToolTip.text: root.t("lock")
                PlasmaComponents.ToolTip.visible: hovered
            }
            PlasmaComponents.ToolButton {
                visible: session.canLogout
                icon.name: "system-log-out"
                onClicked: {
                    root.expanded = false;
                    session.requestLogout();
                }
                Accessible.name: root.t("logout")
                PlasmaComponents.ToolTip.text: root.t("logout")
                PlasmaComponents.ToolTip.visible: hovered
            }
            PlasmaComponents.ToolButton {
                visible: session.canReboot
                icon.name: "system-reboot"
                onClicked: {
                    root.expanded = false;
                    session.requestReboot();
                }
                Accessible.name: root.t("restart")
                PlasmaComponents.ToolTip.text: root.t("restart")
                PlasmaComponents.ToolTip.visible: hovered
            }
            PlasmaComponents.ToolButton {
                visible: session.canShutdown
                icon.name: "system-shutdown"
                onClicked: {
                    root.expanded = false;
                    session.requestShutdown();
                }
                Accessible.name: root.t("shutdown")
                PlasmaComponents.ToolTip.text: root.t("shutdown")
                PlasmaComponents.ToolTip.visible: hovered
            }
        }
    }
}
