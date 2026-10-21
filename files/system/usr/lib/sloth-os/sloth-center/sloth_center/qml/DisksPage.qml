// Disks: the drives' usage and health, deleting unneeded files.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Disks")

    actions: [
        Kirigami.Action {
            text: L.t("Refresh")
            icon.name: "view-refresh"
            onTriggered: disks.refresh()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Repeater {
            model: disks.drives
            delegate: Kirigami.AbstractCard {
                id: card
                required property var modelData
                Layout.fillWidth: true
                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.largeSpacing
                    RowLayout {
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: card.modelData.kind === L.t("Removable drive") ? "drive-removable-media" : "drive-harddisk"
                            implicitWidth: Kirigami.Units.iconSizes.large
                            implicitHeight: Kirigami.Units.iconSizes.large
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Kirigami.Heading {
                                level: 3
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: card.modelData.system ? L.t("System disk") : card.modelData.name
                            }
                            QQC2.Label {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                opacity: 0.7
                                text: card.modelData.kind + (card.modelData.system ? " · " + card.modelData.name : "")
                                      + (card.modelData.temp > 0 ? " · " + card.modelData.temp + " °C" : "")
                            }
                        }
                        Kirigami.Chip {
                            checkable: false
                            closable: false
                            icon.name: card.modelData.health === "ok" ? "checkmark" : "dialog-warning"
                            text: card.modelData.health === "ok" ? L.t("Healthy") : L.t("May be failing!")
                        }
                    }
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        visible: card.modelData.usedPercent > 0
                        from: 0; to: 100
                        value: card.modelData.usedPercent
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        QQC2.Label { Layout.fillWidth: true; text: card.modelData.usageText }
                        QQC2.Button {
                            visible: card.modelData.openPath !== ""
                            text: L.t("Open")
                            icon.name: "folder-open"
                            onClicked: disks.openFolder(card.modelData.openPath)
                        }
                    }
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        visible: card.modelData.health !== "ok"
                        type: Kirigami.MessageType.Error
                        text: L.t("According to its own self-check, this drive may fail. Copy your important files somewhere else as soon as possible!")
                    }
                }
            }
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("Delete unneeded files") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: disks.cleanupText !== "" ? disks.cleanupText
                              : L.t("Removes system components no app uses anymore (for example, left over after deleting an app). Your files aren't touched.")
                    }
                }
                QQC2.BusyIndicator {
                    visible: disks.busy
                    running: visible
                }
                QQC2.Button {
                    enabled: !disks.busy
                    icon.name: "edit-clear-all"
                    text: L.t("Clean up")
                    onClicked: disks.cleanup()
                }
            }
        }

        // --- Bringing files over from Windows (only if there is a Windows partition) --------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: disks.hasWindows
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("Bring files over from Windows") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("Copies the Desktop, Documents, Pictures and your other personal folders, plus browser bookmarks, from the Windows on this computer. Windows itself isn't touched, it's only read.")
                    }
                }
                QQC2.Button {
                    icon.name: "folder-download"
                    text: L.t("Bring over…")
                    onClicked: disks.importFromWindows()
                }
            }
        }
    }
}
