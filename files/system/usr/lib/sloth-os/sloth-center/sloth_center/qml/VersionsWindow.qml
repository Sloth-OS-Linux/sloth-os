// „Korábbi verziók”: egy fájl vagy mappa mentett állapotai (versions.py; Dolphin, jobb klikk).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: L.t("Korábbi verziók") + " – " + versions.fileName
    visible: true
    width: Kirigami.Units.gridUnit * 40
    height: Kirigami.Units.gridUnit * 30
    minimumWidth: Kirigami.Units.gridUnit * 26
    minimumHeight: Kirigami.Units.gridUnit * 18
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    pageStack.initialPage: Kirigami.ScrollablePage {
        id: page

        header: ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            RowLayout {
                Layout.margins: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: "view-history"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        level: 2
                        elide: Text.ElideMiddle
                        text: versions.fileName
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                        opacity: 0.7
                        text: versions.folder
                    }
                }
                QQC2.BusyIndicator {
                    visible: versions.busy
                    running: visible
                }
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                visible: versions.errorText !== ""
                type: Kirigami.MessageType.Error
                text: versions.errorText
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                visible: versions.infoText !== ""
                type: Kirigami.MessageType.Positive
                text: versions.infoText
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                visible: !versions.enabled && versions.problem !== "unsupported"
                type: Kirigami.MessageType.Warning
                text: L.t("Az automatikus mentés ki van kapcsolva, ezért nem készülnek új mentett állapotok.")
                actions: Kirigami.Action {
                    text: L.t("Beállítások")
                    icon.name: "configure"
                    onTriggered: versions.openSettings()
                }
            }
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: versions.problem !== ""
            icon.name: "view-history"
            text: versions.problem === "none" ? L.t("Még nincs mentett korábbi verzió")
                  : L.t("Erről nem készül mentés")
            explanation: {
                switch (versions.problem) {
                case "none":
                    return L.t("A mentés óránként készül, és erről még nem készült. Nézz vissza később.");
                case "outside":
                    return L.t("A mentés a saját mappádban lévő fájlokra vonatkozik (Dokumentumok, Képek, Asztal…), a pendrive-okra és a többi lemezre nem.");
                case "excluded":
                    return L.t("A játékok és az átmeneti fájlok nem kerülnek a mentésbe, mert bármikor újra letölthetők.");
                case "pending":
                    return L.t("A mentés a következő újraindítás után indul.");
                default:
                    return L.t("Ezen a gépen nem érhető el: a rendszerlemez fájlrendszere nem támogatja.");
                }
            }
        }

        ListView {
            id: list
            visible: versions.problem === ""
            model: versions.versions
            delegate: QQC2.ItemDelegate {
                id: item
                required property var modelData
                required property int index
                width: ListView.view.width
                hoverEnabled: false
                down: false
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: item.modelData.dateText
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            visible: text !== ""
                            opacity: 0.7
                            text: item.modelData.detail
                        }
                    }
                    QQC2.Button {
                        text: L.t("Megnyitás")
                        icon.name: versions.isDir ? "folder-open" : "document-open"
                        onClicked: versions.open(item.index)
                    }
                    QQC2.Button {
                        visible: versions.isDir && item.modelData.deleted !== 0
                        enabled: !versions.busy
                        text: L.t("Törölt elemek visszahozása")
                        icon.name: "edit-undo"
                        onClicked: versions.restoreDeleted(item.index)
                    }
                    QQC2.Button {
                        enabled: !versions.busy && !item.modelData.current
                        text: L.t("Visszaállítás…")
                        icon.name: "document-revert"
                        onClicked: { confirmRestore.index = item.index; confirmRestore.open(); }
                    }
                    QQC2.ToolButton {
                        icon.name: "overflow-menu"
                        enabled: !versions.busy
                        onClicked: menu.popup()
                        QQC2.Menu {
                            id: menu
                            QQC2.MenuItem {
                                text: L.t("Mentés másolatként")
                                icon.name: "edit-copy"
                                onTriggered: versions.saveCopy(item.index)
                            }
                        }
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirmRestore
        property int index: -1
        title: L.t("Visszaállítod ezt a változatot?")
        subtitle: versions.isDir
                  ? L.t("A megváltozott és a törölt fájlok visszakerülnek; a mostani változatuk a Kukába kerül, onnan visszahozható. Az azóta létrehozott fájlok megmaradnak.")
                  : L.t("A mostani változat a Kukába kerül, onnan visszahozható.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Visszaállítás")
                icon.name: "document-revert"
                onTriggered: { confirmRestore.close(); versions.restore(confirmRestore.index); }
            },
            Kirigami.Action {
                text: L.t("Mégse")
                icon.name: "dialog-cancel"
                onTriggered: confirmRestore.close()
            }
        ]
    }
}
