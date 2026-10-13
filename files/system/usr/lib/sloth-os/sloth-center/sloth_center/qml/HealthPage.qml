// Rendszer egészség: "Mi a baj?" emberi nyelven, színes állapotjelzéssel.
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: "Rendszer egészség"

    actions: [
        Kirigami.Action {
            text: "Újra ellenőrzés"
            icon.name: "view-refresh"
            enabled: !health.busy
            onTriggered: health.check()
        },
        Kirigami.Action {
            text: "Napló mentése"
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
                      : health.summary === "Minden rendben van" ? "security-high"
                      : health.summary === "Pár dologra érdemes figyelni" ? "security-medium" : "security-low"
            }
            ColumnLayout {
                Layout.fillWidth: true
                Kirigami.Heading { text: health.busy ? "Ellenőrzés…" : health.summary }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: "Megnéztük, mi történt a gépen, mióta bekapcsoltad."
                }
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: health.savedPath !== ""
            text: "A napló elmentve: " + health.savedPath + ". Ezt a fájlt küldd el annak, aki segít."
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
        title: "Napló mentése"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "txt"
        currentFile: StandardPaths.writableLocation(StandardPaths.DesktopLocation) + "/sloth-os-naplo.txt"
        nameFilters: ["Szövegfájl (*.txt)"]
        onAccepted: health.saveLog(selectedFile.toString())
    }
}
