// Rendszer egészség: "Mi a baj?" emberi nyelven, színes állapotjelzéssel.
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Rendszer egészség")

    actions: [
        Kirigami.Action {
            text: L.t("Újra ellenőrzés")
            icon.name: "view-refresh"
            enabled: !health.busy
            onTriggered: health.check()
        },
        Kirigami.Action {
            text: L.t("Napló mentése")
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
                Kirigami.Heading { text: health.busy ? L.t("Ellenőrzés…") : health.summary }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Megnéztük, mi történt a gépen, mióta bekapcsoltad.")
                }
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: health.savedPath !== ""
            text: L.tf("A napló elmentve: {path}. Ezt a fájlt küldd el annak, aki segít.", { path: health.savedPath })
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
        title: L.t("Napló mentése")
        fileMode: FileDialog.SaveFile
        defaultSuffix: "txt"
        // a fájlnév a felület nyelvén (csak ASCII betűk, hogy bárhová el lehessen küldeni)
        currentFile: StandardPaths.writableLocation(StandardPaths.DesktopLocation) + "/" + L.t("sloth-os-naplo.txt")
        nameFilters: [L.t("Szövegfájl (*.txt)")]
        onAccepted: health.saveLog(selectedFile.toString())
    }
}
