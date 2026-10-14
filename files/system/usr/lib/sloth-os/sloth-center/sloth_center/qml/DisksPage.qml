// Lemezek: meghajtók foglaltsága és egészsége, felesleges fájlok törlése.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Lemezek")

    actions: [
        Kirigami.Action {
            text: L.t("Frissítés")
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
                            source: card.modelData.kind === L.t("Cserélhető meghajtó") ? "drive-removable-media" : "drive-harddisk"
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
                                text: card.modelData.system ? L.t("Rendszerlemez") : card.modelData.name
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
                            text: card.modelData.health === "ok" ? L.t("Egészséges") : L.t("Hibás lehet!")
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
                            text: L.t("Megnyitás")
                            icon.name: "folder-open"
                            onClicked: disks.openFolder(card.modelData.openPath)
                        }
                    }
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        visible: card.modelData.health !== "ok"
                        type: Kirigami.MessageType.Error
                        text: L.t("Ez a meghajtó a saját önellenőrzése szerint meghibásodhat. Mentsd el minél előbb a fontos fájljaidat egy másik helyre!")
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
                    Kirigami.Heading { level: 3; text: L.t("Felesleges fájlok törlése") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: disks.cleanupText !== "" ? disks.cleanupText
                              : L.t("Törli azokat a rendszerösszetevőket, amelyeket már egyetlen app sem használ (például egy törölt app után maradtak). A fájljaidhoz nem nyúl.")
                    }
                }
                QQC2.BusyIndicator {
                    visible: disks.busy
                    running: visible
                }
                QQC2.Button {
                    enabled: !disks.busy
                    icon.name: "edit-clear-all"
                    text: L.t("Takarítás")
                    onClicked: disks.cleanup()
                }
            }
        }
    }
}
