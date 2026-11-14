// System status: how the computer is, on one page. At the top what the check-up found (health.py: "What is wrong?"
// in plain language), then the version and the updates, the check-up's points (services, programs that crashed,
// memory, the graphics card, the disks, the temperature; each with a button to the page that helps), the network,
// the download speed limit, security and storage. Until 2026-11-14 the check-up had a page of its own (System
// health), which asked nearly the same question with the same icon.
import QtCore
import QtQuick
import QtQuick.Dialogs
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    property var navigation
    title: L.t("System status")

    readonly property var storage: health.results.find(item => item.id === "disk") || null
    readonly property var network: health.results.find(item => item.id === "network") || null
    readonly property bool secure: updates.signatureVerified && health.security.length > 0
                                   && health.security.every(item => item.state === "ok")
    // the check-up's points that have no card of their own below (the network and the storage do)
    readonly property var checks: health.results.filter(item => item.id !== "network" && item.id !== "disk")

    actions: [
        Kirigami.Action {
            text: L.t("Check again")
            icon.name: "view-refresh"
            enabled: !health.busy
            onTriggered: health.check()
        },
        Kirigami.Action {
            text: L.t("Save log")
            icon.name: "document-save"
            onTriggered: saveDialog.open()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        // --- What the check-up found ----------------------------------------------------------------
        RowLayout {
            spacing: Kirigami.Units.largeSpacing * 2
            Kirigami.Icon {
                implicitWidth: Kirigami.Units.iconSizes.huge
                implicitHeight: Kirigami.Units.iconSizes.huge
                source: health.busy ? "view-refresh"
                      : health.level === "ok" ? "security-high"
                      : health.level === "warning" ? "security-medium" : "security-low"
            }
            ColumnLayout {
                Layout.fillWidth: true
                Kirigami.Heading { Layout.fillWidth: true; wrapMode: Text.Wrap; text: health.busy ? L.t("Checking…") : health.summary }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("We looked at what happened on the computer since you turned it on.")
                }
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: health.savedPath !== ""
            text: L.tf("Log saved: {path}. Send this file to whoever is helping you.", { path: health.savedPath })
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: "sloth-os"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { text: L.t("Sloth OS"); level: 3 }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: L.tf("Version: {version}", { version: updates.currentVersion || "–" })
                    }
                }
            }
        }

        UpdatesCard {}

        // --- The check-up's points, one row each (a colored mark: fine, look at it, a problem) --------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: page.checks.length > 0
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { text: L.t("System health"); level: 3 }
                Repeater {
                    model: page.checks
                    delegate: RowLayout {
                        id: check
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Rectangle {
                            implicitWidth: Kirigami.Units.smallSpacing * 1.5
                            Layout.fillHeight: true
                            radius: width / 2
                            color: check.modelData.state === "error" ? Kirigami.Theme.negativeTextColor
                                 : check.modelData.state === "warning" ? Kirigami.Theme.neutralTextColor
                                 : Kirigami.Theme.positiveTextColor
                        }
                        Kirigami.Icon {
                            source: check.modelData.icon
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { text: check.modelData.title; font.bold: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                opacity: check.modelData.state === "ok" ? 0.7 : 1
                                text: check.modelData.text
                            }
                        }
                        // a point can lead to the page that helps (e.g. "backup", "services"); the button is its name
                        QQC2.Button {
                            readonly property int target: page.navigation && check.modelData.action
                                ? page.navigation.modules.findIndex(m => m.id === check.modelData.action) : -1
                            visible: target >= 0
                            text: target >= 0 ? page.navigation.modules[target].name : ""
                            icon.name: target >= 0 ? page.navigation.modules[target].icon : ""
                            onClicked: page.navigation.openModule(target)
                        }
                    }
                }
            }
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: page.network ? page.network.icon : "network-wired"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { text: L.t("Network"); level: 3 }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: page.network ? page.network.text
                              : health.busy ? L.t("Checking…") : L.t("Network status is not available.")
                    }
                    QQC2.Button {
                        text: L.t("Check Wi-Fi")
                        icon.name: "network-wireless"
                        onClicked: { wifiCheck.open(); wifi.check(); }
                    }
                }
            }
        }

        // --- The download speed limit (netlimit.py): every download of the computer, no password needed ---
        Kirigami.AbstractCard {
            id: limitCard
            Layout.fillWidth: true
            // a change takes effect a moment after the last click or key press, not at every step of the number
            function apply() { limitTimer.restart() }
            Timer {
                id: limitTimer
                interval: 700
                onTriggered: netlimit.set(limitSwitch.checked, limitValue.value, netlimit.state.units[limitUnit.currentIndex],
                                          limitAlways.checked ? "always" : "updates")
            }
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Kirigami.Heading { level: 3; text: L.t("Download speed limit"); Layout.fillWidth: true }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.7
                            text: L.t("Limits how fast this computer downloads, so the rest of your home network stays fast: for a call, a game or another computer. It applies always, or only while updates download.")
                        }
                    }
                    QQC2.Switch {
                        id: limitSwitch
                        Accessible.name: L.t("Download speed limit")
                        checked: netlimit.state.on
                        onToggled: limitCard.apply()
                    }
                }
                RowLayout {
                    enabled: limitSwitch.checked
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.SpinBox {
                        id: limitValue
                        // the number in the chosen unit; whole numbers (0.5 MB/s is 500 KB/s)
                        from: 1; to: 100000; editable: true
                        value: Math.max(1, Math.round(netlimit.state.value))
                        Accessible.name: L.t("Download speed limit")
                        onValueModified: limitCard.apply()
                    }
                    QQC2.ComboBox {
                        id: limitUnit
                        // the units are the same in every language
                        model: ["kbit/s", "KB/s", "Mbit/s", "MB/s"]
                        currentIndex: Math.max(0, netlimit.state.units.indexOf(netlimit.state.unit))
                        onActivated: limitCard.apply()
                    }
                }
                RowLayout {
                    enabled: limitSwitch.checked
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.RadioButton {
                        id: limitAlways
                        text: L.t("Always")
                        checked: netlimit.state.when === "always"
                        onToggled: limitCard.apply()
                    }
                    QQC2.RadioButton {
                        text: L.t("Only while updates download")
                        checked: netlimit.state.when === "updates"
                        onToggled: limitCard.apply()
                    }
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: netlimit.error !== ""
                    type: Kirigami.MessageType.Warning
                    text: netlimit.error
                }
            }
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    Layout.alignment: Qt.AlignTop
                    source: page.secure ? "security-high" : "security-medium"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { text: L.t("Security"); level: 3 }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        visible: health.busy && health.security.length === 0
                        text: L.t("Checking…")
                    }
                    Repeater {
                        model: health.security
                        delegate: QQC2.Label {
                            required property var modelData
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: modelData.text
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: updates.signatureVerified
                              ? L.t("Updates are signature-checked: only versions signed by Sloth OS are installed.")
                              : L.t("The update signature check is not active yet. It turns on by itself in the background.")
                    }
                }
            }
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: "drive-harddisk"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { text: L.t("Available storage"); level: 3 }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: page.storage && page.storage.state !== "ok" ? page.storage.text
                            : page.storage && page.storage.freeText !== "" ? page.storage.freeText
                              : health.busy ? L.t("Checking storage…") : L.t("Storage information is not available.")
                    }
                }
            }
        }

        QQC2.Button {
            Layout.alignment: Qt.AlignHCenter
            text: L.t("Get help")
            icon.name: "mail-message-new"
            onClicked: navigation.openModuleById("help")
        }
    }

    component UpdatesCard: Kirigami.AbstractCard {
        Layout.fillWidth: true
        contentItem: RowLayout {
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon {
                source: updates.busy ? "system-software-update"
                      : updates.needsReboot ? "system-reboot"
                      : updates.updateAvailable ? "update-high" : "security-high"
                implicitWidth: Kirigami.Units.iconSizes.large
                implicitHeight: Kirigami.Units.iconSizes.large
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    level: 3
                    text: updates.busy ? updates.statusText
                        : updates.needsReboot ? L.t("Restart needed")
                        : updates.updateAvailable ? L.t("A new update is available")
                        : L.t("Your system is up to date")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: updates.needsReboot && !updates.busy
                          ? L.tf("After a restart, this starts: {version}", { version: updates.pendingVersion })
                          : updates.updateAvailable && !updates.busy
                          ? L.tf("Available version: {version}", { version: updates.availableVersion })
                          : updates.busy ? updates.statusText : L.t("System update status")
                }
            }
        }
    }

    FileDialog {
        id: saveDialog
        title: L.t("Save log")
        fileMode: FileDialog.SaveFile
        defaultSuffix: "txt"
        // the file name in the interface's language (only ASCII letters, so it can be sent anywhere)
        currentFile: StandardPaths.writableLocation(StandardPaths.DesktopLocation) + "/" + L.t("sloth-os-log.txt")
        nameFilters: [L.t("Text file (*.txt)")]
        onAccepted: health.saveLog(selectedFile.toString())
    }

    // The Wi-Fi check (wifi.py): the steps one under the other; the last one that is not right has a button
    Kirigami.Dialog {
        id: wifiCheck
        title: L.t("Wi-Fi check")
        preferredWidth: Kirigami.Units.gridUnit * 30
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Check again")
                icon.name: "view-refresh"
                enabled: !wifi.busy
                onTriggered: wifi.check()
            },
            Kirigami.Action {
                text: L.t("Close")
                icon.name: "dialog-close"
                onTriggered: wifiCheck.close()
            }
        ]

        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing

            RowLayout {
                visible: wifi.busy
                spacing: Kirigami.Units.largeSpacing
                QQC2.BusyIndicator { running: wifi.busy }
                QQC2.Label { text: L.t("Checking…") }
            }

            Repeater {
                model: wifi.busy ? [] : wifi.steps
                delegate: RowLayout {
                    id: stepRow
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignTop
                        source: stepRow.modelData.state === "ok" ? "emblem-ok-symbolic"
                              : stepRow.modelData.state === "warning" ? "emblem-warning" : "emblem-error"
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        QQC2.Label { text: stepRow.modelData.title; font.bold: true }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: stepRow.modelData.text
                        }
                        QQC2.Button {
                            visible: stepRow.modelData.action !== ""
                            highlighted: true
                            icon.name: stepRow.modelData.action === "turnOn" ? "network-wireless"
                                     : stepRow.modelData.action === "networks" ? "network-wireless-connected-75"
                                     : stepRow.modelData.action === "portal" ? "internet-web-browser"
                                     : "preferences-devices-cpu"
                            text: stepRow.modelData.action === "turnOn" ? L.t("Turn on Wi-Fi")
                                : stepRow.modelData.action === "networks" ? L.t("Choose a network")
                                : stepRow.modelData.action === "portal" ? L.t("Open the sign-in page")
                                : L.t("Drivers and hardware")
                            onClicked: {
                                if (stepRow.modelData.action === "drivers") {
                                    wifiCheck.close();
                                    page.navigation.openModule(page.navigation.modules.findIndex(m => m.id === "drivers"));
                                } else {
                                    wifi.act(stepRow.modelData.action);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
