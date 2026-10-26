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
}
