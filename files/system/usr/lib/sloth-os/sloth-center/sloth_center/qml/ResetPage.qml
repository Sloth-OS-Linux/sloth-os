// Resetting the computer: "Keep my files" or "Remove everything" (reset.py).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Reset this PC")

    // "" (choosing), "keep" or "all" (the summary of the chosen mode)
    property string choice: ""

    readonly property var lists: ({
        keep: {
            title: L.t("Keep my files"),
            stays: [
                L.t("Your files (Documents, Pictures, Downloads and the rest)"),
                L.t("App data and games: if you reinstall them, everything will be there"),
                L.t("Accounts, Wi-Fi passwords and saved states")
            ],
            goes: [
                L.t("Installed apps (after the restart you can choose them again in Welcome)"),
                L.t("Desktop settings (theme, taskbar, wallpaper). The old ones are moved to the “Old settings” folder."),
                L.t("System settings, manually added system packages and kernel parameters")
            ]
        },
        all: {
            title: L.t("Remove everything"),
            stays: [
                L.t("Language, time zone, keyboard and disk encryption")
            ],
            goes: [
                L.t("All accounts, and every file in them"),
                L.t("All apps, settings, Wi-Fi passwords and saved states")
            ]
        }
    })

    readonly property string accountProblem: {
        if (choice !== "all")
            return ""
        if (usernameField.text === "")
            return L.t("Enter a username.")
        const bad = reset.checkAccount(usernameField.text)
        if (bad !== "")
            return bad
        if (passwordField.text === "")
            return L.t("Enter a password.")
        if (passwordField.text !== password2Field.text)
            return L.t("The two passwords don't match.")
        return ""
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: reset.errorText !== ""
            type: Kirigami.MessageType.Error
            text: reset.errorText
        }

        // --- Preparation in progress --------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: reset.busy
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Preparing the reset") }
                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: reset.statusText }
                QQC2.ProgressBar { Layout.fillWidth: true; indeterminate: true }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("You can keep working in the meantime.")
                }
            }
        }

        // --- Prepared: waiting for a restart ---------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: !reset.busy && reset.pendingMode !== ""
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: "system-reboot"
                        implicitWidth: Kirigami.Units.iconSizes.large
                        implicitHeight: Kirigami.Units.iconSizes.large
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading { level: 3; text: L.t("Everything is ready") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: L.t("The reset happens at the next restart, before login. It takes a few minutes, and the computer restarts once on its own.")
                        }
                    }
                }
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    QQC2.Button {
                        icon.name: "dialog-cancel"
                        text: L.t("Cancel, I don't want it")
                        onClicked: reset.cancel()
                    }
                    QQC2.Button {
                        icon.name: "system-reboot"
                        text: L.t("Restart now")
                        onClicked: reset.restartNow()
                    }
                }
            }
        }

        // --- Choosing --------------------------------------------------------------------------
        Repeater {
            model: [
                { mode: "keep", icon: "edit-undo", title: L.t("Keep my files"),
                  text: L.t("The system and apps go back to factory state, your files stay. Useful if something isn't working right.") },
                { mode: "all", icon: "edit-delete", title: L.t("Remove everything"),
                  text: L.t("All accounts and files are deleted, the computer will be like freshly installed. Useful before selling or giving it away.") }
            ]
            delegate: Kirigami.AbstractCard {
                id: option
                required property var modelData
                Layout.fillWidth: true
                visible: !reset.busy && reset.pendingMode === "" && page.choice === ""
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: option.modelData.icon
                        implicitWidth: Kirigami.Units.iconSizes.large
                        implicitHeight: Kirigami.Units.iconSizes.large
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading { level: 3; text: option.modelData.title }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: option.modelData.text
                        }
                    }
                    QQC2.Button {
                        text: L.t("Start…")
                        onClicked: page.choice = option.modelData.mode
                    }
                }
            }
        }

        // --- The chosen mode: what stays, what is deleted ------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: !reset.busy && reset.pendingMode === "" && page.choice !== ""
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 2; text: page.choice ? page.lists[page.choice].title : "" }

                QQC2.Label { text: L.t("What stays:"); font.bold: true }
                Repeater {
                    model: page.choice ? page.lists[page.choice].stays : []
                    delegate: RowLayout {
                        id: stay
                        required property string modelData
                        Layout.fillWidth: true
                        Kirigami.Icon {
                            source: "checkmark"
                            isMask: true
                            color: Kirigami.Theme.positiveTextColor
                            Layout.alignment: Qt.AlignTop
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                        }
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: stay.modelData }
                    }
                }

                QQC2.Label { text: L.t("What gets deleted:"); font.bold: true }
                Repeater {
                    model: page.choice ? page.lists[page.choice].goes : []
                    delegate: RowLayout {
                        id: goes
                        required property string modelData
                        Layout.fillWidth: true
                        Kirigami.Icon {
                            source: "edit-delete"
                            Layout.alignment: Qt.AlignTop
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                        }
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: goes.modelData }
                    }
                }

                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("First we download the newest Sloth OS version, so the computer restarts with it.")
                }

                // Backup: in "keep" mode a saved state is made by itself (factory-reset boot), in "all" mode
                // the backups on the machine are deleted too, so you have to back up to an external disk
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: page.choice !== ""
                    type: page.choice === "all" ? Kirigami.MessageType.Warning : Kirigami.MessageType.Information
                    text: page.choice === "all"
                          ? L.t("The saved states on this computer will be deleted too. Copy anything you need to an external drive or USB stick first, otherwise there will be nothing to restore it from.")
                          : backup.state === "ready"
                            ? L.t("Before the reset, we automatically create a saved state of your files. If anything is missing afterwards, you can bring it back from the “Previous versions” menu.")
                            : L.t("File backup doesn't work on this computer, so we can't create a saved state first. Copy anything important to an external drive or USB stick.")
                    actions: [
                        Kirigami.Action {
                            visible: page.choice === "all" || backup.state !== "ready"
                            icon.name: backup.pikaInstalled ? "document-open" : "plasmadiscover"
                            text: backup.pikaInstalled ? L.t("Open Pika Backup") : L.t("Install Pika Backup")
                            onTriggered: backup.pikaInstalled ? backup.openPika() : backup.installPika()
                        }
                    ]
                }
                QQC2.CheckBox {
                    id: savedCheck
                    Layout.fillWidth: true
                    visible: page.choice === "all"
                    text: L.t("I've saved everything I need")
                }

                // "Remove everything": the new account (after the restart you sign in with it)
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: page.choice === "all"
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("The new account") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("You'll sign in with this after the restart. If you give the computer away, the new owner can create their own account later.")
                    }
                    QQC2.TextField {
                        id: fullnameField
                        Layout.fillWidth: true
                        placeholderText: L.t("Full name")
                    }
                    QQC2.TextField {
                        id: usernameField
                        Layout.fillWidth: true
                        placeholderText: L.t("Username (e.g. anna)")
                    }
                    QQC2.TextField {
                        id: passwordField
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: L.t("Password")
                    }
                    QQC2.TextField {
                        id: password2Field
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: L.t("Password again")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        visible: page.accountProblem !== "" && (usernameField.text !== "" || passwordField.text !== "")
                        color: Kirigami.Theme.negativeTextColor
                        text: page.accountProblem
                    }
                }

                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    QQC2.Button {
                        icon.name: "go-previous"
                        text: L.t("Back")
                        onClicked: { page.choice = ""; savedCheck.checked = false }
                    }
                    QQC2.Button {
                        icon.name: "edit-undo"
                        enabled: page.accountProblem === "" && (page.choice !== "all" || savedCheck.checked)
                        text: L.t("Reset…")
                        onClicked: confirm.open()
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirm
        title: L.t("Are you sure you want to reset this PC?")
        subtitle: page.choice === "all"
                  ? L.t("All accounts and files will be permanently deleted. This can't be undone.")
                  : L.t("Installed apps and settings will be deleted, your files stay.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: page.choice === "all" ? L.t("Remove everything") : L.t("Reset this PC")
                icon.name: page.choice === "all" ? "edit-delete" : "edit-undo"
                onTriggered: {
                    confirm.close()
                    reset.start(page.choice, fullnameField.text, usernameField.text, passwordField.text)
                    passwordField.text = ""
                    password2Field.text = ""
                    savedCheck.checked = false
                    page.choice = ""
                }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirm.close()
            }
        ]
    }
}
