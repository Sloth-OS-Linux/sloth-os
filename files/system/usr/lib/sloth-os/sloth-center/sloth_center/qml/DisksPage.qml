// Disks: the drives' usage and health, deleting unneeded files.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    property var navigation
    title: L.t("Disks")

    // Breeze colors, distinct in light and dark mode too
    readonly property var usageColors: ({ files: "#3daee9", games: "#f67400", windows: "#9b59b6", apps: "#27ae60",
                                          cache: "#fdbc4b", system: "#7f8c8d" })
    readonly property int keptVersions: updates.versions.filter(v => v.pinned && !v.booted).length

    Component.onCompleted: {
        if (!disks.usage.items) disks.measure()
        if (!netfolders.searched) netfolders.search()
        sharing.refresh()
    }

    actions: [
        Kirigami.Action {
            text: L.t("Refresh")
            icon.name: "view-refresh"
            onTriggered: disks.refresh()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        // --- What uses the space on the system disk ---------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    Kirigami.Heading { Layout.fillWidth: true; level: 3; text: L.t("What uses the space") }
                    QQC2.Button {
                        enabled: !disks.usageBusy
                        icon.name: "view-refresh"
                        text: L.t("Calculate again")
                        onClicked: disks.measure()
                    }
                }
                RowLayout {
                    visible: disks.usageBusy
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.BusyIndicator { running: parent.visible }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: L.t("Calculating… this can take a minute.")
                    }
                }
                // One bar, a part for each kind
                Rectangle {
                    id: usageBar
                    Layout.fillWidth: true
                    visible: (disks.usage.items || []).length > 0
                    implicitHeight: Kirigami.Units.gridUnit
                    radius: height / 2
                    clip: true
                    color: Kirigami.Theme.alternateBackgroundColor
                    Row {
                        anchors.fill: parent
                        Repeater {
                            model: disks.usage.items || []
                            delegate: Rectangle {
                                required property var modelData
                                width: usageBar.width * modelData.percent / 100
                                height: usageBar.height
                                color: page.usageColors[modelData.id] || Kirigami.Theme.disabledTextColor
                            }
                        }
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: Kirigami.Units.largeSpacing
                    Repeater {
                        model: disks.usage.items || []
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.smallSpacing
                            Rectangle {
                                implicitWidth: Kirigami.Units.smallSpacing * 3
                                implicitHeight: implicitWidth
                                radius: width / 2
                                color: page.usageColors[modelData.id] || Kirigami.Theme.disabledTextColor
                            }
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: modelData.name }
                            QQC2.Label { text: modelData.size; opacity: 0.8 }
                        }
                    }
                }
                QQC2.Label {
                    visible: disks.usage.free !== undefined
                    text: L.tf("{free} free of {total}", { free: disks.usage.free || "", total: disks.usage.total || "" })
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: page.keptVersions > 0
                    type: Kirigami.MessageType.Information
                    text: L.tf("{n} kept system version(s) take up extra space. If everything works, you can stop keeping the ones you no longer need.", { n: page.keptVersions })
                    actions: Kirigami.Action {
                        text: L.t("Show versions")
                        icon.name: "system-software-update"
                        onTriggered: page.navigation.openModule(page.navigation.modules.findIndex(m => m.id === "updates"))
                    }
                }
            }
        }

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

        // --- Network folders: a NAS or another computer's shared folder in the side panel (netfolders.py) ----
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading { level: 3; text: L.t("Network folders") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: L.t("A NAS or another computer's shared folder, in the side panel of the file manager. It stays there after a restart too.")
                        }
                    }
                    QQC2.BusyIndicator {
                        visible: netfolders.searching || netfolders.adding
                        running: visible
                    }
                    QQC2.Button {
                        enabled: !netfolders.searching
                        icon.name: "network-workgroup"
                        text: L.t("Search the network")
                        onClicked: netfolders.search()
                    }
                }

                // The ones already added
                Repeater {
                    model: netfolders.folders
                    delegate: RowLayout {
                        id: folderRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "folder-network"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: implicitWidth
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: folderRow.modelData.name; font.bold: true }
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideMiddle; opacity: 0.7; text: folderRow.modelData.url }
                        }
                        QQC2.Button {
                            text: L.t("Open")
                            icon.name: "folder-open"
                            onClicked: netfolders.open(folderRow.modelData.url)
                        }
                        QQC2.Button {
                            text: L.t("Remove")
                            icon.name: "list-remove"
                            QQC2.ToolTip.visible: hovered
                            QQC2.ToolTip.text: L.t("Only from the side panel. The files on the network aren't touched.")
                            onClicked: netfolders.removeFolder(folderRow.modelData.url)
                        }
                    }
                }

                // Found on the network (Avahi), not added yet
                Repeater {
                    model: netfolders.found
                    delegate: RowLayout {
                        id: foundRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "network-server"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: implicitWidth
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: foundRow.modelData.name; font.bold: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                opacity: foundRow.modelData.shares === 0 ? 1 : 0.7
                                color: foundRow.modelData.shares === 0 ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.textColor
                                text: foundRow.modelData.shares === 0
                                      ? L.t("Found on your network, but it shares no folder now. Turn on sharing in its settings.")
                                      : L.t("Found on your network")
                            }
                        }
                        QQC2.Button {
                            enabled: !netfolders.adding
                            text: L.t("Add")
                            icon.name: "list-add"
                            onClicked: netfolders.addFolder(foundRow.modelData.url, foundRow.modelData.name)
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: !netfolders.searching && netfolders.searched && netfolders.found.length === 0
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("No other computer shares folders on your network, or it doesn't announce itself. Type its address below.")
                }

                // By address: \\NAS\Photos, smb://…, nfs://…
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.TextField {
                        id: addressField
                        Layout.fillWidth: true
                        placeholderText: L.tf("Address, e.g. {example}", { example: "\\\\NAS\\Photos" })
                        onAccepted: if (netfolders.isValid(text) && !netfolders.adding) netfolders.addFolder(text, "")
                    }
                    QQC2.Button {
                        enabled: netfolders.isValid(addressField.text) && !netfolders.adding
                        text: L.t("Add")
                        icon.name: "list-add"
                        onClicked: netfolders.addFolder(addressField.text, "")
                    }
                    Connections {
                        target: netfolders
                        function onAdded() { addressField.text = "" }
                    }
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: netfolders.message !== ""
                    type: netfolders.problem ? Kirigami.MessageType.Warning : Kirigami.MessageType.Information
                    text: netfolders.message
                }
            }
        }

        // --- Sharing a folder on the home network; turning it on always asks for the password (sharing.py) ----
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading { level: 3; text: L.t("Share a folder") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: L.t("Other computers at home (Windows, Mac, a TV) can open the folder. Only your home network can reach it, never the internet.")
                        }
                    }
                    QQC2.BusyIndicator {
                        visible: sharing.busy
                        running: visible
                    }
                }

                // The folders shared now
                Repeater {
                    model: sharing.shares
                    delegate: RowLayout {
                        id: shareRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "folder-remote"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: implicitWidth
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideMiddle; text: shareRow.modelData.path; font.bold: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                opacity: 0.7
                                text: L.tf("Open it from another computer: {address}", { address: shareRow.modelData.address })
                                      + (shareRow.modelData.guests ? " · " + L.t("Without a password") : "")
                                      + (shareRow.modelData.write ? " · " + L.t("Others can change files too") : "")
                            }
                        }
                        QQC2.Button {
                            enabled: !sharing.busy
                            text: L.t("Stop sharing")
                            icon.name: "list-remove"
                            onClicked: sharing.removeShare(shareRow.modelData.name)
                        }
                    }
                }

                QQC2.CheckBox {
                    id: shareGuests
                    text: L.t("Without a password (anyone on your home network)")
                }
                QQC2.CheckBox {
                    id: shareWrite
                    text: L.t("Others can change files too")
                }
                Kirigami.PasswordField {
                    id: sharePassword
                    Layout.fillWidth: true
                    visible: !shareGuests.checked
                    placeholderText: L.t("Password for other computers")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: !shareGuests.checked
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.tf("Other computers sign in with your user name ({user}) and this password.", { user: sharing.user })
                          + (sharing.hasPassword ? " " + L.t("Leave it empty to keep the current password.") : "")
                }
                QQC2.Button {
                    enabled: !sharing.busy && (shareGuests.checked || sharing.hasPassword || sharePassword.text !== "")
                    icon.name: "folder-remote"
                    text: L.t("Choose a folder to share…")
                    onClicked: pickShareFolder.open()
                }
                FolderDialog {
                    id: pickShareFolder
                    title: L.t("Choose a folder to share…")
                    onAccepted: {
                        sharing.addShare(selectedFolder.toString(), shareWrite.checked, shareGuests.checked,
                                         shareGuests.checked ? "" : sharePassword.text)
                        sharePassword.text = ""
                    }
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: sharing.message !== ""
                    type: sharing.problem ? Kirigami.MessageType.Warning : Kirigami.MessageType.Information
                    text: sharing.message
                }
            }
        }

        // --- Deleting unneeded files: measured first, reviewed item by item (cleanup.py) -----
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading { level: 3; text: L.t("Delete unneeded files") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: disks.scanning ? L.t("Looking for unneeded files…")
                                  : disks.cleanupItems.length > 0 ? L.t("Choose what to delete. Your own files are only deleted if you tick them.")
                                  : disks.cleanupText !== "" ? disks.cleanupText
                                  : L.t("Shows what could be deleted and how much space it frees, before anything is deleted. Your files, the previous system version and the kept ones aren't touched.")
                        }
                    }
                    QQC2.BusyIndicator {
                        visible: disks.busy || disks.scanning
                        running: visible
                    }
                    QQC2.Button {
                        visible: disks.cleanupItems.length === 0
                        enabled: !disks.busy && !disks.scanning
                        icon.name: "edit-clear-all"
                        text: L.t("Clean up…")
                        onClicked: disks.scanCleanup()
                    }
                }

                // The items to review, with their size; the ticked ones are deleted
                Repeater {
                    model: disks.cleanupItems
                    delegate: RowLayout {
                        id: itemRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.CheckBox {
                            Layout.alignment: Qt.AlignTop
                            checked: itemRow.modelData.selected
                            Accessible.name: itemRow.modelData.name
                            onToggled: disks.setCleanupSelected(itemRow.modelData.id, checked)
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: itemRow.modelData.name; font.bold: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                opacity: 0.7
                                text: itemRow.modelData.description
                            }
                        }
                        QQC2.Label {
                            Layout.alignment: Qt.AlignTop
                            text: itemRow.modelData.size
                        }
                    }
                }
                RowLayout {
                    visible: disks.cleanupItems.length > 0
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        highlighted: true
                        enabled: disks.cleanupItems.some(i => i.selected)
                        icon.name: "edit-delete"
                        text: disks.selectedSize !== "" ? L.tf("Delete the selected ones ({size})", { size: disks.selectedSize })
                                                         : L.t("Delete the selected ones")
                        onClicked: disks.cleanupSelected()
                    }
                    QQC2.Button {
                        text: L.t("Cancel")
                        icon.name: "dialog-cancel"
                        onClicked: disks.cancelCleanup()
                    }
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
