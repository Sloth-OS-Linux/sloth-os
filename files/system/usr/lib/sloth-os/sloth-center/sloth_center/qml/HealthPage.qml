// System health: "What is wrong?" in plain language, with colored status indicators.
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("System health")

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
                Kirigami.Heading { text: health.busy ? L.t("Checking…") : health.summary }
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

        Repeater {
            model: health.results
            delegate: Kirigami.AbstractCard {
                id: card
                required property var modelData
                Layout.fillWidth: true
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Rectangle {
                        implicitWidth: Kirigami.Units.smallSpacing * 1.5
                        Layout.fillHeight: true
                        radius: width / 2
                        color: card.modelData.state === "error" ? Kirigami.Theme.negativeTextColor
                             : card.modelData.state === "warning" ? Kirigami.Theme.neutralTextColor
                             : Kirigami.Theme.positiveTextColor
                    }
                    Kirigami.Icon {
                        source: card.modelData.icon
                        implicitWidth: Kirigami.Units.iconSizes.medium
                        implicitHeight: Kirigami.Units.iconSizes.medium
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        QQC2.Label { text: card.modelData.title; font.bold: true }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: card.modelData.state === "ok" ? 0.7 : 1
                            text: card.modelData.text
                        }
                    }
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
}
