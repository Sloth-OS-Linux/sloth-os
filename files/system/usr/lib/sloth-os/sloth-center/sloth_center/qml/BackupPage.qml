// Fájlmentés: a saját fájlok óránkénti mentése, a mentett állapotok böngészése (backup.py).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Fájlmentés")

    // a mentett állapotok közül alapból csak a legutóbbiak látszanak
    property bool showAll: false
    readonly property int shortList: 6

    actions: [
        Kirigami.Action {
            text: L.t("Frissítés")
            icon.name: "view-refresh"
            onTriggered: backup.refresh()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: backup.state !== "ready"
            type: backup.state === "pending" ? Kirigami.MessageType.Information : Kirigami.MessageType.Warning
            text: backup.state === "pending" ? L.t("A mentés a következő újraindítás után indul.")
                  : L.t("Ezen a gépen nem érhető el: a rendszerlemez fájlrendszere nem támogatja.")
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: backup.errorText !== ""
            type: Kirigami.MessageType.Error
            text: backup.errorText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: backup.infoText !== ""
            type: Kirigami.MessageType.Positive
            text: backup.infoText
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            enabled: backup.state !== "unsupported" && !backup.busy
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: "backup"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("Automatikus mentés") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("Óránként elmenti a saját fájljaid állapotát. Ha valamit véletlenül törölsz vagy felülírsz, a fájlkezelőben kattints rá jobb gombbal, és válaszd a „Korábbi verziók” lehetőséget.")
                    }
                }
                QQC2.Switch {
                    checked: backup.enabled
                    onToggled: backup.setEnabled(checked)
                }
            }
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            enabled: backup.state !== "unsupported" && !backup.busy
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Mentett állapotok megtartása") }
                Repeater {
                    model: [
                        { keep: "2w", text: L.t("2 hétig") },
                        { keep: "1m", text: L.t("1 hónapig") },
                        { keep: "3m", text: L.t("3 hónapig") }
                    ]
                    delegate: QQC2.RadioButton {
                        required property var modelData
                        text: modelData.text
                        checked: backup.keep === modelData.keep
                        onClicked: backup.setKeep(modelData.keep)
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Az utolsó nap minden órája megmarad, utána naponta, majd hetente egy. Ha kevés a hely a lemezen, a legrégebbiek hamarabb törlődnek.")
                }
            }
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: backup.state === "ready"
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Kirigami.Heading { level: 3; text: L.t("Mentett állapotok") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: backup.snapshots.length === 0
                                  ? L.t("Még nincs mentett állapot. Az első egy órán belül elkészül.")
                                  : L.tf("{n} mentett állapot", { n: backup.snapshots.length })
                        }
                    }
                    QQC2.BusyIndicator {
                        visible: backup.busy
                        running: visible
                    }
                    QQC2.Button {
                        enabled: !backup.busy
                        icon.name: "document-save"
                        text: L.t("Mentés most")
                        onClicked: backup.takeNow()
                    }
                }
                Repeater {
                    model: page.showAll ? backup.snapshots : backup.snapshots.slice(0, page.shortList)
                    delegate: RowLayout {
                        id: row
                        required property var modelData
                        Layout.fillWidth: true
                        Kirigami.Icon {
                            source: "view-history"
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }
                        QQC2.Label { Layout.fillWidth: true; text: row.modelData.dateText }
                        QQC2.Button {
                            visible: row.modelData.path !== ""
                            text: L.t("Megnyitás")
                            icon.name: "folder-open"
                            onClicked: backup.openFolder(row.modelData.path)
                        }
                    }
                }
                QQC2.Button {
                    visible: !page.showAll && backup.snapshots.length > page.shortList
                    flat: true
                    icon.name: "go-down"
                    text: L.t("Az összes mutatása")
                    onClicked: page.showAll = true
                }
                QQC2.Button {
                    visible: backup.snapshots.length > 0
                    enabled: !backup.busy
                    icon.name: "edit-delete"
                    text: L.t("Az összes mentett állapot törlése…")
                    onClicked: confirmDelete.open()
                }
            }
        }

        // --- Mentés külső lemezre (Pika Backup) -----------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: "drive-removable-media"
                        implicitWidth: Kirigami.Units.iconSizes.large
                        implicitHeight: Kirigami.Units.iconSizes.large
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading { level: 3; text: L.t("Mentés külső lemezre") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: L.t("A Pika Backup rendszeresen átmásolja a fájljaidat egy külső lemezre vagy pendrive-ra. Ha a gép elromlik vagy elveszik, onnan minden visszahozható, egy korábbi állapot is. Ingyenes, és a mentést jelszóval is védheted.")
                        }
                    }
                }
                QQC2.Label { text: L.t("Így állítsd be:"); font.bold: true }
                Repeater {
                    model: [
                        L.t("Telepítsd, majd nyisd meg a Pika Backupot."),
                        L.t("Dugd be a külső lemezt, és válaszd ki mentési helynek."),
                        L.t("Állítsd be, milyen gyakran mentsen. Onnantól magától ment, amikor a lemez csatlakoztatva van.")
                    ]
                    delegate: RowLayout {
                        id: step
                        required property string modelData
                        required property int index
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        QQC2.Label { text: (step.index + 1) + "."; Layout.alignment: Qt.AlignTop }
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: step.modelData }
                    }
                }
                QQC2.Button {
                    Layout.alignment: Qt.AlignRight
                    icon.name: backup.pikaInstalled ? "document-open" : "plasmadiscover"
                    text: backup.pikaInstalled ? L.t("Pika Backup megnyitása") : L.t("Pika Backup telepítése")
                    onClicked: backup.pikaInstalled ? backup.openPika() : backup.installPika()
                }
            }
        }

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("A játékok és az átmeneti fájlok nem kerülnek a mentésbe, mert bármikor újra letölthetők.") + " "
                  + L.t("A mentett állapotok ugyanazon a lemezen vannak, mint a fájljaid: ha a lemez tönkremegy, ezek is elvesznek. A fontos fájlokat ezért időnként másold egy külső lemezre is.")
        }
    }

    Kirigami.PromptDialog {
        id: confirmDelete
        title: L.t("Törlöd az összes mentett állapotot?")
        subtitle: L.t("Ezután a korábbi verziók nem lesznek elérhetők. A mostani fájljaidhoz nem nyúl.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Törlés")
                icon.name: "edit-delete"
                onTriggered: { confirmDelete.close(); backup.deleteAll(); }
            },
            Kirigami.Action {
                text: L.t("Mégse")
                icon.name: "dialog-cancel"
                onTriggered: confirmDelete.close()
            }
        ]
    }
}
