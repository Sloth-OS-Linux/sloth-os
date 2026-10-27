// File backup: hourly backups of your own files, browsing the saved states (backup.py).
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("File backup")

    // of the saved states only the latest ones are shown by default
    property bool showAll: false
    readonly property int shortList: 6

    actions: [
        Kirigami.Action {
            text: L.t("Refresh")
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
            text: backup.state === "pending" ? L.t("Backups will start after the next restart.")
                  : L.t("Not available on this computer: the system disk's file system doesn't support it.")
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
                    Kirigami.Heading { level: 3; text: L.t("Automatic backup") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("Saves the state of your own files every hour. If you accidentally delete or overwrite something, right-click it in the file manager and choose “Previous versions”.")
                    }
                }
                QQC2.Switch {
                    checked: backup.enabled
                    onToggled: backup.setEnabled(checked)
                }
            }
        }

        // The "Previous versions" window without knowing the right-click menu: pick the file, or the folder of a
        // deleted one
        RowLayout {
            visible: backup.snapshots.length > 0
            spacing: Kirigami.Units.largeSpacing
            QQC2.Button {
                icon.name: "document-revert"
                text: L.t("Restore a file…")
                onClicked: pickFile.open()
            }
            QQC2.Button {
                icon.name: "edit-undo"
                text: L.t("Find deleted files…")
                onClicked: pickFolder.open()
            }
            QQC2.Button {
                icon.name: "checkmark"
                text: L.t("Check the backup")
                enabled: backup.verifyState !== "checking"
                onClicked: backup.verify()
            }
        }
        // The result of "Check the backup": a sample of the latest saved state read back
        RowLayout {
            Layout.fillWidth: true
            visible: backup.verifyText !== ""
            spacing: Kirigami.Units.largeSpacing
            QQC2.BusyIndicator {
                visible: backup.verifyState === "checking"
                running: visible
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: Kirigami.Units.iconSizes.smallMedium
            }
            Kirigami.Icon {
                visible: backup.verifyState !== "checking"
                source: backup.verifyState === "ok" ? "emblem-ok-symbolic" : "emblem-warning"
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: Kirigami.Units.iconSizes.smallMedium
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: backup.verifyText
            }
        }
        FileDialog {
            id: pickFile
            title: L.t("Choose the file to restore")
            currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
            onAccepted: backup.showVersions(selectedFile.toString())
        }
        FolderDialog {
            id: pickFolder
            title: L.t("Choose the folder the files were in")
            currentFolder: StandardPaths.writableLocation(StandardPaths.HomeLocation)
            onAccepted: backup.showVersions(selectedFolder.toString())
        }

        // --- Sloth OS's own settings in one file, for a reinstalled or another computer (settings_backup.py) ---
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Sloth OS settings") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Save the look, the display and sound profiles and the other Sloth OS settings to a file, and load them after reinstalling or on another computer. Your files are not in it.")
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: settingsBackup.resultText !== ""
                    type: settingsBackup.resultOk ? Kirigami.MessageType.Positive : Kirigami.MessageType.Error
                    text: settingsBackup.resultText
                }
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        icon.name: "document-save"
                        text: L.t("Save settings to a file…")
                        onClicked: saveSettings.open()
                    }
                    QQC2.Button {
                        icon.name: "document-open"
                        text: L.t("Load settings from a file…")
                        onClicked: loadSettings.open()
                    }
                }
            }
        }
        FileDialog {
            id: saveSettings
            fileMode: FileDialog.SaveFile
            title: L.t("Save Sloth OS settings")
            nameFilters: [L.t("Sloth OS settings") + " (*.json)"]
            currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
            selectedFile: currentFolder + "/" + settingsBackup.suggestedName
            onAccepted: settingsBackup.exportTo(selectedFile.toString())
        }
        FileDialog {
            id: loadSettings
            title: L.t("Load Sloth OS settings")
            nameFilters: [L.t("Sloth OS settings") + " (*.json)"]
            currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
            onAccepted: settingsBackup.importFrom(selectedFile.toString())
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            enabled: backup.state !== "unsupported" && !backup.busy
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Keep saved states for") }
                Repeater {
                    model: [
                        { keep: "2w", text: L.t("2 weeks") },
                        { keep: "1m", text: L.t("1 month") },
                        { keep: "3m", text: L.t("3 months") }
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
                    text: L.t("Every hour of the last day is kept, then one per day, then one per week. If the disk is running out of space, the oldest ones are deleted sooner.")
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
                        Kirigami.Heading { level: 3; text: L.t("Saved states") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: backup.snapshots.length === 0
                                  ? L.t("No saved states yet. The first one will be made within an hour.")
                                  : L.tf("{n} saved states", { n: backup.snapshots.length })
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            visible: backup.snapshots.length > 0
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: L.tf("Last backup: {date}", { date: backup.snapshots.length ? backup.snapshots[0].dateText : "" })
                        }
                    }
                    QQC2.BusyIndicator {
                        visible: backup.busy
                        running: visible
                    }
                    QQC2.Button {
                        enabled: !backup.busy
                        icon.name: "document-save"
                        text: L.t("Back up now")
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
                            text: L.t("Open")
                            icon.name: "folder-open"
                            onClicked: backup.openFolder(row.modelData.path)
                        }
                    }
                }
                QQC2.Button {
                    visible: !page.showAll && backup.snapshots.length > page.shortList
                    flat: true
                    icon.name: "go-down"
                    text: L.t("Show all")
                    onClicked: page.showAll = true
                }
                QQC2.Button {
                    visible: backup.snapshots.length > 0
                    enabled: !backup.busy
                    icon.name: "edit-delete"
                    text: L.t("Delete all saved states…")
                    onClicked: confirmDelete.open()
                }
            }
        }

        // --- Backup to an external disk (Pika Backup) -----------------------------------------------
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
                        Kirigami.Heading { level: 3; text: L.t("Back up to an external drive") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: L.t("Pika Backup regularly copies your files to an external drive or USB stick. If the computer breaks or gets lost, everything can be brought back from there, even an earlier state. It's free, and you can protect the backup with a password.")
                        }
                    }
                }
                QQC2.Label { text: L.t("How to set it up:"); font.bold: true }
                Repeater {
                    model: [
                        L.t("Install Pika Backup, then open it."),
                        L.t("Plug in the external drive and choose it as the backup location."),
                        L.t("Set how often it should back up. From then on it backs up by itself whenever the drive is connected.")
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
                    text: backup.pikaInstalled ? L.t("Open Pika Backup") : L.t("Install Pika Backup")
                    onClicked: backup.pikaInstalled ? backup.openPika() : backup.installPika()
                }
            }
        }

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("Games and temporary files are not backed up, because they can be downloaded again at any time.") + " "
                  + L.t("The saved states are on the same disk as your files: if the disk fails, they are lost too. So copy your important files to an external drive from time to time as well.")
        }
    }

    Kirigami.PromptDialog {
        id: confirmDelete
        title: L.t("Delete all saved states?")
        subtitle: L.t("After this, previous versions will not be available. Your current files are not touched.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Delete")
                icon.name: "edit-delete"
                onTriggered: { confirmDelete.close(); backup.deleteAll(); }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirmDelete.close()
            }
        ]
    }
}
