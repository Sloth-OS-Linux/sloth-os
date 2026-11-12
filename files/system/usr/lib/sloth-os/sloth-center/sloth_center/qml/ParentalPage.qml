// Parental controls: child accounts, their screen time and the apps they may open (family.py).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Parental controls")

    // A half-hour step as "16:30" in the user's own time format; 48 (24:00) is midnight at the end of the day
    function slotText(i) {
        if (i >= 48)
            return L.t("midnight");
        return Qt.formatTime(new Date(2000, 0, 1, Math.floor(i / 2), (i % 2) * 30), Qt.locale().timeFormat(Locale.ShortFormat));
    }

    actions: [
        Kirigami.Action {
            text: L.t("Refresh")
            icon.name: "view-refresh"
            onTriggered: family.refresh()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("Make an account for each child. Here you choose how long and when they can use the computer, and which apps they can open. Without your password, children can't install apps or change the computer's settings.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Information
            visible: !family.isAdmin
            text: L.t("Only a parent (an administrator account) can change parental controls.")
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Information
            visible: !family.isAdmin && family.ownTimeText !== ""
            text: family.ownTimeText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Warning
            visible: family.isAdmin && family.autologinWarning !== "" && family.children.length > 0
            text: family.autologinWarning
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: family.errorText !== ""
            text: family.errorText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: family.infoText !== "" && !family.busy
            text: family.infoText
        }
        QQC2.ProgressBar {
            Layout.fillWidth: true
            visible: family.busy
            indeterminate: true
        }

        // --- The children ----------------------------------------------------------------------
        Repeater {
            model: family.isAdmin ? family.children : []
            delegate: Kirigami.AbstractCard {
                id: card
                required property var modelData
                Layout.fillWidth: true
                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.largeSpacing

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "user-identity"
                            implicitWidth: Kirigami.Units.iconSizes.large
                            implicitHeight: Kirigami.Units.iconSizes.large
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Kirigami.Heading { level: 3; text: card.modelData.name }
                            QQC2.Label {
                                opacity: 0.7
                                text: card.modelData.user + (card.modelData.signedIn ? " · " + L.t("signed in") : "")
                            }
                        }
                        QQC2.Button {
                            icon.name: "edit-delete"
                            text: L.t("Delete account")
                            enabled: !family.busy
                            onClicked: { confirmRemove.target = card.modelData.user; confirmRemove.targetName = card.modelData.name; confirmRemove.open(); }
                        }
                    }

                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: !card.modelData.readable
                        wrapMode: Text.Wrap
                        color: Kirigami.Theme.negativeTextColor
                        text: L.t("Couldn't read this account's parental controls. Restart the computer and try again.")
                    }

                    // Screen time
                    Kirigami.Heading { level: 4; text: L.t("Screen time") }
                    GridLayout {
                        columns: 2
                        columnSpacing: Kirigami.Units.largeSpacing
                        enabled: !family.busy && card.modelData.readable

                        QQC2.Label { text: L.t("Daily limit") }
                        QQC2.ComboBox {
                            id: daily
                            model: family.dailyChoices.map(m => family.durationText(m))
                            currentIndex: Math.max(0, family.dailyChoices.indexOf(card.modelData.daily))
                            onActivated: (index) => family.setScreenTime(card.modelData.user, family.dailyChoices[index],
                                                                        schedule.checked, start.currentIndex, end.currentIndex + 1)
                        }

                        QQC2.CheckBox {
                            id: schedule
                            text: L.t("Only at certain hours")
                            checked: card.modelData.scheduleOn
                            onToggled: family.setScreenTime(card.modelData.user, family.dailyChoices[daily.currentIndex],
                                                            checked, start.currentIndex, end.currentIndex + 1)
                        }
                        RowLayout {
                            enabled: schedule.checked
                            QQC2.ComboBox {
                                id: start
                                model: Array.from({ length: 48 }, (_, i) => page.slotText(i))
                                currentIndex: card.modelData.start
                                onActivated: family.setScreenTime(card.modelData.user, family.dailyChoices[daily.currentIndex],
                                                                  true, currentIndex, end.currentIndex + 1)
                            }
                            QQC2.Label { text: "–" }
                            QQC2.ComboBox {
                                id: end
                                model: Array.from({ length: 48 }, (_, i) => page.slotText(i + 1))
                                currentIndex: card.modelData.end - 1
                                onActivated: family.setScreenTime(card.modelData.user, family.dailyChoices[daily.currentIndex],
                                                                  true, start.currentIndex, currentIndex + 1)
                            }
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: card.modelData.used !== ""
                        opacity: 0.7
                        text: card.modelData.used
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: L.t("A few minutes before the time is up, the child gets a warning, then the computer signs them out. They can ask for more time: you allow it with your password on their screen.")
                    }

                    // Websites (family-web: the child's name lookups go through a family filter)
                    Kirigami.Heading { level: 4; text: L.t("Websites") }
                    QQC2.CheckBox {
                        Layout.fillWidth: true
                        text: L.t("Block adult websites and use safe search")
                        checked: card.modelData.web
                        enabled: !family.busy
                        onToggled: family.setWebFilter(card.modelData.user, checked)
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: L.t("Works in every browser and app. Google, Bing and YouTube show only family-friendly results, and websites for adults, proxies and VPNs don't open. The filter is CleanBrowsing's family filter; your own account is not filtered.")
                    }

                    // Apps
                    Kirigami.Heading { level: 4; text: L.t("Apps") }
                    QQC2.CheckDelegate {
                        Layout.fillWidth: true
                        icon.name: "application-x-ms-dos-executable"
                        text: L.t("Windows programs and downloaded apps")
                        checked: card.modelData.programs
                        enabled: !family.busy && card.modelData.readable
                        onToggled: family.setProgramsAllowed(card.modelData.user, checked)
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: family.apps.length > 0
                              ? L.t("Turn off the apps this child may not open. Apps you install later are allowed until you turn them off here.")
                              : L.t("No apps are installed yet. Install apps in Discover or Sloth Welcome, then come back here.")
                    }
                    Repeater {
                        model: family.apps
                        delegate: QQC2.CheckDelegate {
                            id: appRow
                            required property var modelData
                            Layout.fillWidth: true
                            icon.name: modelData.id
                            text: modelData.name
                            checked: card.modelData.blocked.indexOf(modelData.id) < 0
                            enabled: !family.busy && card.modelData.readable
                            onToggled: family.setAppAllowed(card.modelData.user, modelData.id, checked)
                        }
                    }
                }
            }
        }

        // --- A new child account ---------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: family.isAdmin
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Add a child account") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("The child signs in with their own name and password, and gets their own desktop and files. They can't install apps or change settings without your password.")
                }
                Kirigami.FormLayout {
                    Layout.fillWidth: true
                    QQC2.TextField {
                        id: fullName
                        Kirigami.FormData.label: L.t("Name:")
                        onTextEdited: if (!userName.edited) userName.text = family.suggestUsername(text)
                    }
                    QQC2.TextField {
                        id: userName
                        property bool edited: false
                        Kirigami.FormData.label: L.t("Username:")
                        validator: RegularExpressionValidator { regularExpression: /[a-z_][a-z0-9_-]{0,31}/ }
                        onTextEdited: edited = text !== ""
                    }
                    Kirigami.PasswordField {
                        id: password
                        Kirigami.FormData.label: L.t("Password:")
                    }
                    Kirigami.PasswordField {
                        id: password2
                        Kirigami.FormData.label: L.t("Password again:")
                        onAccepted: createButton.clicked()
                    }
                }
                QQC2.Button {
                    id: createButton
                    Layout.alignment: Qt.AlignRight
                    icon.name: "list-add-user"
                    text: L.t("Create account")
                    enabled: !family.busy && fullName.text.trim() !== "" && userName.text !== "" && password.text !== ""
                    onClicked: {
                        family.addChild(fullName.text, userName.text, password.text, password2.text);
                        password.text = "";
                        password2.text = "";
                    }
                }
            }
        }

        Connections {
            target: family
            function onChildAdded() {
                fullName.text = "";
                userName.text = "";
                userName.edited = false;
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirmRemove
        property string target: ""
        property string targetName: ""
        title: L.tf("Delete {name}'s account?", { name: targetName })
        subtitle: L.t("Their files (documents, pictures, game saves) are deleted too, and this can't be undone. If they are signed in, they are signed out first.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Delete")
                icon.name: "edit-delete"
                onTriggered: { family.removeChild(confirmRemove.target); confirmRemove.close(); }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirmRemove.close()
            }
        ]
    }
}
