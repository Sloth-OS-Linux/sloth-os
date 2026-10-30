// Installed Windows programs: list, start, files, repair, move, remove,
// the install location, and taking over programs installed elsewhere (Steam, Lutris, Bottles, an earlier install).
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Programs")

    actions: [
        Kirigami.Action {
            text: L.t("Install a program…")
            icon.name: "download"
            onTriggered: installDialog.open()
        },
        Kirigami.Action {
            text: L.t("Refresh")
            icon.name: "view-refresh"
            onTriggered: winprograms.refresh()
        }
    ]

    ListView {
        id: list
        model: winprograms.programs
        spacing: Kirigami.Units.smallSpacing

        header: ColumnLayout {
            width: ListView.view.width
            spacing: Kirigami.Units.smallSpacing

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: winprograms.message !== ""
                type: Kirigami.MessageType.Information
                text: winprograms.message
            }

            QQC2.ProgressBar {
                Layout.fillWidth: true
                visible: winprograms.busy
                indeterminate: true
            }

            // Where programs are installed
            Kirigami.AbstractCard {
                Layout.fillWidth: true
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: "folder-games"
                        implicitWidth: Kirigami.Units.iconSizes.medium
                        implicitHeight: Kirigami.Units.iconSizes.medium
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Kirigami.Heading {
                            level: 3
                            Layout.fillWidth: true
                            text: L.tf("Programs location: {path}", { path: winprograms.location })
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.7
                            text: L.t("Each program gets its own folder; open it with the Files button. To keep them somewhere else (for example on another drive), choose a new location: new programs go there, and existing ones can be moved one by one.")
                        }
                    }
                    QQC2.Button {
                        text: L.t("Change…")
                        icon.name: "folder-open"
                        onClicked: locationDialog.open()
                    }
                }
            }

            // Shared knowledge: anonymous sharing of the settings that worked (off by default)
            Kirigami.AbstractCard {
                Layout.fillWidth: true
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: "network-workgroup"
                        implicitWidth: Kirigami.Units.iconSizes.medium
                        implicitHeight: Kirigami.Units.iconSizes.medium
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Kirigami.Heading { level: 3; text: L.t("Share experiences"); Layout.fillWidth: true }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.7
                            text: L.t("When a program starts on your computer, we anonymously share which setting worked, so it starts on the first try on other Sloth OS computers too. Only the setting and your graphics card's manufacturer are sent: not your name, not your files, not the program's name.")
                        }
                    }
                    QQC2.Switch {
                        checked: winprograms.sharing
                        onToggled: winprograms.setSharing(checked)
                    }
                }
            }

            // Taking over programs installed elsewhere (Steam, Lutris, Bottles, an earlier install)
            Kirigami.AbstractCard {
                Layout.fillWidth: true
                visible: winprograms.otherPrograms.length > 0
                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing
                    RowLayout {
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "document-import"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Kirigami.Heading { level: 3; text: L.t("Programs installed elsewhere"); Layout.fillWidth: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                opacity: 0.7
                                text: L.t("You installed these in Steam, Lutris, Bottles or earlier in some other way. You can add them here too, without reinstalling. “With the original app”: it keeps starting them, just like before. “Take over”: they get their own copy and start on their own. Nothing changes in their original place either way.")
                            }
                        }
                    }
                    Repeater {
                        model: winprograms.otherPrograms
                        delegate: RowLayout {
                            id: otherRow
                            required property var modelData
                            Layout.fillWidth: true
                            QQC2.Label {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: otherRow.modelData.name
                            }
                            QQC2.Label {
                                opacity: 0.6
                                text: otherRow.modelData.source
                            }
                            QQC2.Button {
                                text: L.t("With the original app")
                                enabled: otherRow.modelData.canLink && !winprograms.busy
                                onClicked: winprograms.importProgram(otherRow.modelData.key, false)
                                QQC2.ToolTip.visible: hovered && !otherRow.modelData.canLink
                                QQC2.ToolTip.text: L.t("No other app starts this program, so it can only be taken over.")
                            }
                            QQC2.Button {
                                text: L.t("Take over")
                                enabled: otherRow.modelData.canAdopt && !winprograms.busy
                                onClicked: winprograms.importProgram(otherRow.modelData.key, true)
                                QQC2.ToolTip.visible: hovered && !otherRow.modelData.canAdopt
                                QQC2.ToolTip.text: L.t("This program has no environment of its own, so it can only be added with the original app.")
                            }
                        }
                    }
                }
            }
        }
        headerPositioning: ListView.InlineHeader

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: list.count === 0
            icon.name: "application-x-ms-dos-executable"
            text: L.t("No Windows programs installed yet")
            explanation: L.t("Double-click an .exe or .msi file (for example a downloaded installer), or use the Install a program… button, and it will show up here.")
        }

        delegate: Kirigami.AbstractCard {
            id: card
            required property var modelData
            readonly property bool isLink: card.modelData.kind === "link"
            width: ListView.view.width
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: card.modelData.icon !== "" ? card.modelData.icon : "application-x-ms-dos-executable"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 3; text: card.modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                    QQC2.Label {
                        Layout.fillWidth: true
                        opacity: 0.7
                        elide: Text.ElideRight
                        text: {
                            const parts = [];
                            if (card.isLink)
                                parts.push(L.tf("Started by: {source}", { source: card.modelData.source }));
                            else if (card.modelData.size !== "" && card.modelData.hasFiles)
                                parts.push(card.modelData.size);
                            if (card.modelData.publisher !== "")
                                parts.push(card.modelData.publisher);
                            const names = card.modelData.entries.map(e => e.name);
                            parts.push(names.length > 0 ? L.tf("In the Start menu: {names}", { names: names.join(", ") }) : L.t("Not in the Start menu"));
                            return parts.join(" · ");
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: card.modelData.hasFiles
                        opacity: 0.5
                        elide: Text.ElideMiddle
                        font: Kirigami.Theme.smallFont
                        text: card.modelData.folder
                    }
                }
                QQC2.Button {
                    visible: !card.modelData.shared
                    highlighted: true
                    text: L.t("Start")
                    icon.name: "media-playback-start"
                    onClicked: winprograms.launch(card.modelData.id)
                }
                QQC2.Button {
                    visible: card.modelData.hasFiles
                    text: L.t("Files")
                    icon.name: "folder-open"
                    onClicked: winprograms.openFolder(card.modelData.id)
                }
                QQC2.ToolButton {
                    icon.name: "overflow-menu"
                    text: L.t("More")
                    display: QQC2.AbstractButton.IconOnly
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.text: text
                    onClicked: moreMenu.popup()
                    QQC2.Menu {
                        id: moreMenu
                        QQC2.MenuItem {
                            visible: card.modelData.kind === "windows"
                            height: visible ? implicitHeight : 0
                            text: L.t("Start menu…")
                            icon.name: "kickoff"
                            onTriggered: winprograms.editShortcuts(card.modelData.id)
                        }
                        QQC2.MenuItem {
                            visible: card.modelData.kind === "windows" && !card.modelData.shared
                            height: visible ? implicitHeight : 0
                            text: L.t("Repair")
                            icon.name: "tools-wizard"
                            onTriggered: winprograms.repair(card.modelData.id)
                        }
                        // Recognized games are ticked by themselves; the user can say otherwise (e.g. Notepad++
                        // is not one, a small indie game is)
                        QQC2.MenuItem {
                            visible: card.modelData.kind === "windows" && !card.modelData.shared
                            height: visible ? implicitHeight : 0
                            text: L.t("It's a game (on the Games page)")
                            checkable: true
                            checked: card.modelData.isGame
                            onTriggered: winprograms.setGame(card.modelData.id, checked)
                        }
                        QQC2.MenuItem {
                            visible: card.modelData.canReinstall
                            height: visible ? implicitHeight : 0
                            text: L.t("Reinstall")
                            icon.name: "view-refresh"
                            onTriggered: winprograms.reinstall(card.modelData.id)
                        }
                        QQC2.MenuItem {
                            visible: card.modelData.canMove
                            height: visible ? implicitHeight : 0
                            text: L.tf("Move to: {path}", { path: winprograms.location })
                            icon.name: "folder-move"
                            enabled: !winprograms.busy
                            onTriggered: winprograms.move(card.modelData.id)
                        }
                        QQC2.MenuSeparator {}
                        QQC2.MenuItem {
                            text: L.t("Remove")
                            icon.name: "edit-delete"
                            onTriggered: {
                                confirm.target = card.modelData;
                                confirm.open();
                            }
                        }
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirm
        property var target: null
        title: target ? L.tf("Remove {name}?", { name: target.name }) : ""
        subtitle: target && target.kind === "link"
                  ? L.t("It only disappears from here and from the Start menu; everything stays in its original place.")
                  : L.t("The program and all its files will be deleted (including saves and settings). This can't be undone.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Remove")
                icon.name: "edit-delete"
                onTriggered: { winprograms.remove(confirm.target.id); confirm.close(); }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirm.close()
            }
        ]
    }

    FileDialog {
        id: installDialog
        title: L.t("Which program do you want to install?")
        currentFolder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
        nameFilters: [L.t("Programs") + " (*.exe *.msi *.EXE *.MSI *.AppImage *.appimage *.deb *.rpm)"]
        onAccepted: winprograms.install(selectedFile.toString())
    }

    FolderDialog {
        id: locationDialog
        title: L.t("Where should new programs be installed?")
        onAccepted: winprograms.setLocation(selectedFolder.toString())
    }
}
