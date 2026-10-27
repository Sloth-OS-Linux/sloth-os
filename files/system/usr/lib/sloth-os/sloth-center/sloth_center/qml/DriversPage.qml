// Drivers and hardware: graphics card, the matching system version, Secure Boot key.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Drivers and hardware")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: drivers.errorText !== ""
            text: drivers.errorText
        }

        // --- Graphics card -------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Graphics card") }
                Repeater {
                    model: drivers.gpus
                    delegate: RowLayout {
                        id: gpuRow
                        required property var modelData
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "video-display"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        QQC2.Label { text: gpuRow.modelData.name; font.bold: true }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    visible: drivers.canSwitch && !drivers.mismatch
                    text: drivers.nvidiaImage
                          ? L.t("The NVIDIA edition of Sloth OS is running and the NVIDIA driver is installed. Everything is fine.")
                          : L.t("The AMD/Intel edition of Sloth OS is running; the drivers are part of the system. Everything is fine.")
                }
            }
        }

        // --- The wrong version runs ---------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: drivers.mismatch || drivers.busy || drivers.infoText === "switched"
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading {
                    level: 3
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: drivers.infoText === "switched" ? L.t("Done! Restart the computer.")
                        : drivers.hasNvidia ? L.t("Switch to the NVIDIA edition")
                        : L.t("Switch to the AMD/Intel edition")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: !drivers.busy && drivers.infoText !== "switched"
                    text: drivers.hasNvidia
                          ? L.t("Your computer has an NVIDIA graphics card, but the AMD/Intel edition of Sloth OS is running. Games run much better with the NVIDIA edition. Your files and settings are kept.")
                          : L.t("Your computer has no NVIDIA graphics card, so the AMD/Intel edition is the better choice. Your files and settings are kept.")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: drivers.infoText === "switched"
                    text: L.t("After a restart, the new edition starts. If something's wrong, you can go back on the Updates page.")
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: drivers.busy
                    QQC2.Label { text: drivers.statusText }
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        from: 0; to: 100
                        value: Math.max(0, drivers.progress)
                        indeterminate: drivers.progress < 0
                    }
                    QQC2.Label { opacity: 0.7; text: drivers.infoText }
                }
                QQC2.Button {
                    visible: !drivers.busy && drivers.infoText !== "switched"
                    highlighted: true
                    icon.name: "download"
                    text: L.t("Switch now")
                    onClicked: drivers.switchVariant()
                }
                QQC2.Button {
                    visible: drivers.infoText === "switched"
                    icon.name: "system-reboot"
                    text: L.t("Restart now")
                    onClicked: updates.reboot()
                }
            }
        }

        // --- Secure Boot key ---------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: drivers.keyNeeded || drivers.keyPending
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading {
                    level: 3
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: drivers.keyPending ? L.t("One more step: restart the computer") : L.t("The NVIDIA driver needs a permission")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: drivers.keyNeeded
                    text: L.t("Secure Boot is turned on on your computer. For the NVIDIA driver to load, the Sloth OS key has to be allowed once. It takes a few clicks, and you never have to deal with it again.")
                }
                QQC2.Button {
                    visible: drivers.keyNeeded
                    highlighted: true
                    icon.name: "security-high"
                    text: L.t("Prepare the permission")
                    onClicked: drivers.enrollKey()
                }
                // Step by step to the blue screen (the machine's firmware shows it, in English)
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: drivers.keyPending
                    spacing: Kirigami.Units.smallSpacing
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: L.t("After restarting, a blue screen appears (in English). Use the arrow keys and Enter there:")
                    }
                    Repeater {
                        model: [
                            L.t("Press a key when “Press any key” is shown."),
                            L.t("Choose “Enroll MOK”."),
                            L.t("Choose “Continue”, then “Yes”."),
                            L.t("Type the password: universalblue (what you type isn't shown on screen)."),
                            L.t("Choose “Reboot”. That's it!")
                        ]
                        delegate: QQC2.Label {
                            required property string modelData
                            required property int index
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: (index + 1) + ". " + modelData
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: L.t("If you accidentally skip it, no problem: the computer starts and this page will offer it again.")
                    }
                    QQC2.Button {
                        icon.name: "system-reboot"
                        text: L.t("Restart now")
                        onClicked: updates.reboot()
                    }
                }
            }
        }

        // --- Controllers ---------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Controllers") }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: gamepads.gamepads.length === 0
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("No controller is connected right now. Plug one in with a cable, or pair it over Bluetooth. Xbox, PlayStation, Nintendo Switch and Steam controllers work without installing anything.")
                }
                Repeater {
                    model: gamepads.gamepads
                    delegate: RowLayout {
                        id: padRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "input-gamepad"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: padRow.modelData.name; font.bold: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                opacity: 0.7
                                text: gamepads.connectionText(padRow.modelData.connection)
                            }
                        }
                        Kirigami.Icon {
                            visible: padRow.modelData.battery >= 0
                            source: padRow.modelData.charging ? "battery-charging" : padRow.modelData.battery < 20 ? "battery-caution" : "battery"
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }
                        QQC2.Label {
                            visible: padRow.modelData.battery >= 0
                            text: padRow.modelData.battery + "%"
                        }
                    }
                }
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        icon.name: "preferences-system-bluetooth"
                        text: L.t("Pair a wireless controller")
                        onClicked: gamepads.openSettings("kcm_bluetooth")
                    }
                    QQC2.Button {
                        enabled: gamepads.gamepads.length > 0
                        icon.name: "input-gamepad"
                        text: L.t("Test the buttons")
                        onClicked: gamepads.openSettings("kcm_gamecontroller")
                    }
                }
            }
        }

        // --- Displays: refresh rate, VRR and HDR for games (displays.py) ---------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: displays.monitors.length > 0
            Component.onCompleted: displays.refresh()
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Displays") }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    type: Kirigami.MessageType.Error
                    visible: displays.errorText !== ""
                    text: displays.errorText
                }
                Repeater {
                    model: displays.monitors
                    delegate: ColumnLayout {
                        id: monitor
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Separator { Layout.fillWidth: true; visible: monitor.index > 0 }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing
                            Kirigami.Icon {
                                source: "video-display"
                                implicitWidth: Kirigami.Units.iconSizes.medium
                                implicitHeight: Kirigami.Units.iconSizes.medium
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                QQC2.Label { text: monitor.modelData.name; font.bold: true }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    opacity: 0.8
                                    text: monitor.modelData.bestHz > monitor.modelData.hz
                                          ? L.tf("{size}, {hz} Hz now. It can do {best} Hz: games look smoother.", { size: monitor.modelData.size, hz: monitor.modelData.hz, best: monitor.modelData.bestHz })
                                          : L.tf("{size}, {hz} Hz (the most it can do).", { size: monitor.modelData.size, hz: monitor.modelData.hz })
                                }
                            }
                            QQC2.Button {
                                visible: monitor.modelData.bestHz > monitor.modelData.hz
                                highlighted: true
                                enabled: !displays.confirming
                                text: L.tf("Use {hz} Hz", { hz: monitor.modelData.bestHz })
                                onClicked: displays.useBestRefresh(monitor.modelData.connector)
                            }
                        }
                        QQC2.Switch {
                            visible: monitor.modelData.vrr !== ""
                            enabled: !displays.confirming
                            text: L.t("Variable refresh rate (FreeSync, G-Sync): smoother games without tearing")
                            checked: monitor.modelData.vrr === "on"
                            onToggled: displays.setVrr(monitor.modelData.connector, checked)
                        }
                        QQC2.Switch {
                            visible: monitor.modelData.hdr !== ""
                            enabled: !displays.confirming
                            text: L.t("HDR: brighter highlights and richer colors in games and videos that support it")
                            checked: monitor.modelData.hdr === "on"
                            onToggled: displays.setHdr(monitor.modelData.connector, checked)
                        }
                    }
                }
                QQC2.Button {
                    icon.name: "preferences-desktop-display"
                    text: L.t("More display settings")
                    onClicked: displays.openSettings()
                }
            }
        }

        // After a display change: keep it, or it goes back by itself (a black screen cannot get stuck)
        Kirigami.PromptDialog {
            id: keepDisplay
            property int left: 15
            title: L.t("Keep this display setting?")
            subtitle: L.tf("If the screen looks right, keep it. Otherwise it goes back by itself in {n} seconds.", { n: keepDisplay.left })
            standardButtons: Kirigami.Dialog.NoButton
            closePolicy: QQC2.Popup.NoAutoClose
            customFooterActions: [
                Kirigami.Action {
                    text: L.t("Keep")
                    icon.name: "dialog-ok"
                    onTriggered: { keepTimer.stop(); keepDisplay.close(); displays.keep(); }
                },
                Kirigami.Action {
                    text: L.t("Go back")
                    icon.name: "edit-undo"
                    onTriggered: { keepTimer.stop(); keepDisplay.close(); displays.revert(); }
                }
            ]
            Timer {
                id: keepTimer
                interval: 1000
                repeat: true
                onTriggered: {
                    keepDisplay.left--;
                    if (keepDisplay.left <= 0) {
                        stop();
                        keepDisplay.close();
                        displays.revert();
                    }
                }
            }
        }
        Connections {
            target: displays
            function onChanged() {
                if (displays.confirming && !keepDisplay.opened) {
                    keepDisplay.left = 15;
                    keepDisplay.open();
                    keepTimer.restart();
                }
            }
        }

        // --- Bluetooth: adapter, on or off, connected devices (bluetooth.py) ----------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: bluetooth.checked
            Component.onCompleted: bluetooth.refresh()
            // follows turning it on and off in the tray too, while the page is open
            Timer {
                interval: 3000
                repeat: true
                running: page.visible && Qt.application.state === Qt.ApplicationActive
                onTriggered: bluetooth.refresh()
            }
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Bluetooth") }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    type: Kirigami.MessageType.Error
                    visible: bluetooth.errorText !== ""
                    text: bluetooth.errorText
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: !bluetooth.adapter || !bluetooth.powered || bluetooth.devices.length === 0
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: !bluetooth.adapter ? L.t("This computer has no Bluetooth. A small USB Bluetooth adapter adds it.")
                          : !bluetooth.powered ? L.t("Bluetooth is turned off.")
                          : L.t("No Bluetooth device is connected right now.")
                }
                Repeater {
                    model: bluetooth.devices
                    delegate: RowLayout {
                        id: btRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: btRow.modelData.icon
                            fallback: "preferences-system-bluetooth"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: btRow.modelData.name; font.bold: true }
                        Kirigami.Icon {
                            visible: btRow.modelData.battery >= 0
                            source: btRow.modelData.battery < 20 ? "battery-caution" : "battery"
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }
                        QQC2.Label {
                            visible: btRow.modelData.battery >= 0
                            text: btRow.modelData.battery + "%"
                        }
                    }
                }
                RowLayout {
                    visible: bluetooth.adapter
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        visible: !bluetooth.powered
                        highlighted: true
                        icon.name: "preferences-system-bluetooth"
                        text: L.t("Turn on Bluetooth")
                        onClicked: bluetooth.turnOn()
                    }
                    QQC2.Button {
                        icon.name: "list-add"
                        text: L.t("Pair a device")
                        onClicked: bluetooth.openSettings()
                    }
                }
            }
        }

        // --- Sound: where it goes, which microphone, and trying both (sound.py) --------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            Component.onCompleted: sound.refresh()
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Sound") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: sound.outputs.length || sound.inputs.length
                          ? L.t("Choose where the sound goes and which microphone games and calls use, then try them.")
                          : L.t("No sound devices were found.")
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: Kirigami.Units.largeSpacing
                    rowSpacing: Kirigami.Units.largeSpacing
                    visible: sound.outputs.length > 0

                    Kirigami.Icon {
                        source: "audio-headphones"
                        implicitWidth: Kirigami.Units.iconSizes.medium
                        implicitHeight: Kirigami.Units.iconSizes.medium
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        QQC2.Label { text: L.t("Speakers or headphones"); font.bold: true }
                        QQC2.ComboBox {
                            Layout.fillWidth: true
                            model: sound.outputs
                            textRole: "label"
                            currentIndex: sound.outputs.findIndex(d => d.name === sound.currentOutput)
                            onActivated: index => sound.setOutput(sound.outputs[index].name)
                        }
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignBottom
                        icon.name: "media-playback-start"
                        text: L.t("Play a test sound")
                        onClicked: sound.playTest()
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: Kirigami.Units.largeSpacing
                    rowSpacing: Kirigami.Units.largeSpacing
                    visible: sound.inputs.length > 0

                    Kirigami.Icon {
                        source: "audio-input-microphone"
                        implicitWidth: Kirigami.Units.iconSizes.medium
                        implicitHeight: Kirigami.Units.iconSizes.medium
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        QQC2.Label { text: L.t("Microphone"); font.bold: true }
                        QQC2.ComboBox {
                            Layout.fillWidth: true
                            enabled: sound.micState !== "recording" && sound.micState !== "playing"
                            model: sound.inputs
                            textRole: "label"
                            currentIndex: sound.inputs.findIndex(d => d.name === sound.currentInput)
                            onActivated: index => sound.setInput(sound.inputs[index].name)
                        }
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignBottom
                        icon.name: "audio-input-microphone"
                        text: L.t("Test the microphone")
                        enabled: sound.micState !== "recording" && sound.micState !== "playing"
                        onClicked: sound.testMic()
                    }
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: sound.inputMuted
                    type: Kirigami.MessageType.Warning
                    text: L.t("This microphone is muted.")
                    actions: [
                        Kirigami.Action {
                            text: L.t("Unmute")
                            icon.name: "audio-input-microphone"
                            onTriggered: sound.unmuteInput()
                        }
                    ]
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: sound.micText !== ""
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.BusyIndicator {
                        visible: sound.micState === "recording" || sound.micState === "playing"
                        running: visible
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                    }
                    Kirigami.Icon {
                        visible: !(sound.micState === "recording" || sound.micState === "playing")
                        source: sound.micState === "ok" ? "emblem-ok-symbolic" : "emblem-warning"
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: sound.micText
                    }
                }
            }
        }

        // --- Connecting a phone (KDE Connect) ------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: drivers.phoneLinkAvailable
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("Connect your phone") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("Your phone's notifications, files and messages on your computer (KDE Connect). Install the KDE Connect app on your phone; both need to be on the same Wi-Fi network.")
                    }
                }
                QQC2.Switch {
                    checked: drivers.phoneLink
                    onToggled: drivers.setPhoneLink(checked)
                }
            }
        }
    }

    // Connecting, disconnecting a controller, battery level: refreshed every few seconds
    Timer {
        interval: 3000
        running: page.visible
        repeat: true
        onTriggered: gamepads.refresh()
    }
}
