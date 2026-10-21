// "Previous versions": the saved states of a file or folder (versions.py; Dolphin, right-click).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: L.t("Previous versions") + " – " + versions.fileName
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
                text: L.t("Automatic backup is turned off, so no new states are being saved.")
                actions: Kirigami.Action {
                    text: L.t("Settings")
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
            text: versions.problem === "none" ? L.t("No saved previous version yet")
                  : L.t("This is not backed up")
            explanation: {
                switch (versions.problem) {
                case "none":
                    return L.t("Backups are made every hour, and there isn't one of this yet. Check back later.");
                case "outside":
                    return L.t("Backups cover the files in your own folder (Documents, Pictures, Desktop…), not USB drives or other disks.");
                case "excluded":
                    return L.t("Games and temporary files are not backed up, because they can be downloaded again at any time.");
                case "pending":
                    return L.t("Backups will start after the next restart.");
                default:
                    return L.t("Not available on this computer: the system disk's file system doesn't support it.");
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
                        text: L.t("Open")
                        icon.name: versions.isDir ? "folder-open" : "document-open"
                        onClicked: versions.open(item.index)
                    }
                    QQC2.Button {
                        visible: versions.isDir && item.modelData.deleted !== 0
                        enabled: !versions.busy
                        text: L.t("Bring back deleted items")
                        icon.name: "edit-undo"
                        onClicked: versions.restoreDeleted(item.index)
                    }
                    QQC2.Button {
                        enabled: !versions.busy && !item.modelData.current
                        text: L.t("Restore…")
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
                                text: L.t("Save as a copy")
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
        title: L.t("Restore this version?")
        subtitle: versions.isDir
                  ? L.t("Changed and deleted files come back; their current versions go to the Trash, where you can get them back. Files created since then are kept.")
                  : L.t("The current version goes to the Trash, where you can get it back.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Restore")
                icon.name: "document-revert"
                onTriggered: { confirmRestore.close(); versions.restore(confirmRestore.index); }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirmRestore.close()
            }
        ]
    }
}
