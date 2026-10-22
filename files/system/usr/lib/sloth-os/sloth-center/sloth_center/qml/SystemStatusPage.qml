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
