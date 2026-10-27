// A quick overview of the running system, updates, storage, and help.
import QtQuick
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

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

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
                        text: page.storage && page.storage.freeText !== "" ? page.storage.freeText
                              : health.busy ? L.t("Checking storage…") : L.t("Storage information is not available.")
                    }
                }
            }
        }

        QQC2.Button {
            Layout.alignment: Qt.AlignHCenter
            text: L.t("Get help")
            icon.name: "mail-message-new"
            onClicked: navigation.openModule(navigation.modules.findIndex(item => item.id === "feedback"))
        }
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
