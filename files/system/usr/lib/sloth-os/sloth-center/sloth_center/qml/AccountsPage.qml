// Account and security: what the system asks a password for (per topic), automatic login, sudo.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Account and security")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: accounts.errorText !== ""
            text: accounts.errorText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: accounts.infoText !== ""
            text: accounts.infoText
        }

        // --- The account -------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: accounts.isAdmin ? "user-admin" : "user-identity"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 3; text: accounts.userName }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: accounts.isAdmin ? L.t("You are an administrator: you can also change the computer's settings.")
                                               : L.t("Standard account: changing the computer's settings needs an administrator's password.")
                    }
                }
                QQC2.Button {
                    icon.name: "preferences-system-users"
                    text: L.t("Manage users")
                    onClicked: accounts.openUsers()
                }
            }
        }

        // --- Sign-in methods (based on the machine's hardware) ------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Ways to sign in") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Your password always works. On top of that, we offer what your computer can do. When you sign in with a fingerprint, a key or a PIN, the store of saved passwords asks for your password the first time it is used.")
                }
                Repeater {
                    model: accounts.loginMethods
                    delegate: RowLayout {
                        id: methodRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        opacity: methodRow.modelData.comingSoon ? 0.6 : 1
                        Kirigami.Icon {
                            source: methodRow.modelData.icon
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; text: methodRow.modelData.name; font.bold: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                opacity: 0.75
                                text: methodRow.modelData.description
                            }
                        }
                        QQC2.Button {
                            visible: methodRow.modelData.id === "fingerprint"
                            icon.name: "list-add"
                            text: L.t("Add fingerprint")
                            onClicked: accounts.openUsers()
                        }
                        QQC2.Button {
                            visible: methodRow.modelData.id === "securitykey"
                            enabled: accounts.busyTask === ""
                            icon.name: "list-add"
                            text: methodRow.modelData.ready ? L.t("Add another key") : L.t("Add key")
                            onClicked: accounts.enrollSecurityKey()
                        }
                        QQC2.Button {
                            visible: methodRow.modelData.id === "pin"
                            icon.name: methodRow.modelData.enabled ? "edit-entry" : "list-add"
                            text: methodRow.modelData.enabled ? L.t("Change PIN") : L.t("Set up PIN")
                            onClicked: { pinField.text = ""; pinField2.text = ""; pinForm.visible = true; pinField.forceActiveFocus() }
                        }
                        QQC2.Button {
                            visible: methodRow.modelData.id === "pin" && methodRow.modelData.enabled
                            icon.name: "edit-delete"
                            text: L.t("Delete")
                            onClicked: accounts.removePin()
                        }
                        QQC2.Switch {
                            visible: !methodRow.modelData.comingSoon && methodRow.modelData.id !== "pin"
                            enabled: methodRow.modelData.ready
                            checked: methodRow.modelData.enabled
                            onToggled: accounts.setLoginMethod(methodRow.modelData.id, checked)
                        }
                    }
                }
                // Entering a PIN (twice, digits only)
                RowLayout {
                    id: pinForm
                    visible: false
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.PasswordField {
                        id: pinField
                        Layout.fillWidth: true
                        placeholderText: L.t("New PIN (4–8 digits)")
                        maximumLength: 8
                        inputMethodHints: Qt.ImhDigitsOnly
                        validator: RegularExpressionValidator { regularExpression: /[0-9]{0,8}/ }
                    }
                    Kirigami.PasswordField {
                        id: pinField2
                        Layout.fillWidth: true
                        placeholderText: L.t("Once more")
                        maximumLength: 8
                        inputMethodHints: Qt.ImhDigitsOnly
                        validator: RegularExpressionValidator { regularExpression: /[0-9]{0,8}/ }
                        onAccepted: pinSave.clicked()
                    }
                    QQC2.Button {
                        id: pinSave
                        icon.name: "document-save"
                        text: L.t("Save")
                        enabled: pinField.text.length >= 4 && pinField2.text.length >= 4
                        onClicked: {
                            accounts.setPin(pinField.text, pinField2.text)
                            pinField.text = ""; pinField2.text = ""
                            if (accounts.errorText === "")
                                pinForm.visible = false
                        }
                    }
                    QQC2.Button {
                        text: L.t("Cancel")
                        onClicked: { pinField.text = ""; pinField2.text = ""; pinForm.visible = false }
                    }
                }
                RowLayout {
                    visible: accounts.busyTask === "securitykey"
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.BusyIndicator { running: parent.visible }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: L.t("Touch the key when it blinks.")
                    }
                }
            }
        }

        // --- Work account (Active Directory) --------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            enabled: accounts.isAdmin
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Work account") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: accounts.domain !== ""
                          ? L.tf("This computer belongs to the {domain} domain: you can also sign in with work accounts.", { domain: accounts.domain })
                          : L.t("If your workplace uses a Windows domain (Active Directory), you can join this computer to it and sign in with your work account. Ask your administrator for the domain name and an account that is allowed to join computers.")
                }
                Kirigami.FormLayout {
                    Layout.fillWidth: true
                    visible: accounts.domain === ""
                    QQC2.TextField {
                        id: domainName
                        Kirigami.FormData.label: L.t("Domain:")
                        placeholderText: L.t("e.g. company.local")
                    }
                    QQC2.TextField {
                        id: domainAdmin
                        Kirigami.FormData.label: L.t("Username:")
                        placeholderText: L.t("an account allowed to join")
                    }
                    Kirigami.PasswordField {
                        id: domainPassword
                        Kirigami.FormData.label: L.t("Password:")
                    }
                }
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        visible: accounts.domain === ""
                        enabled: domainName.text.trim() !== "" && domainAdmin.text.trim() !== "" && domainPassword.text !== "" && accounts.busyTask === ""
                        icon.name: "network-connect"
                        text: L.t("Join")
                        onClicked: { accounts.joinDomain(domainName.text, domainAdmin.text, domainPassword.text); domainPassword.text = ""; }
                    }
                    QQC2.BusyIndicator { visible: accounts.busyTask === "domain"; running: visible }
                    QQC2.Button {
                        visible: accounts.domain !== ""
                        icon.name: "network-disconnect"
                        text: L.t("Leave the domain")
                        onClicked: accounts.leaveDomain()
                    }
                }
            }
        }

        // --- Cloud storage (OneDrive, Google Drive) ------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Cloud storage") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("OneDrive or Google Drive as a folder in your home folder, just like on Windows: all files are visible, but only the ones you open are downloaded. Opened files stay available without internet too.")
                }
                Repeater {
                    model: cloud.drives
                    delegate: RowLayout {
                        id: driveRow
                        // the page is ComponentBehavior: Bound, so the row only sees its data through this (without it
                        // every binding failed: both spinners turned and the buttons did nothing, 2026-10-26)
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: driveRow.modelData.configured
                                  ? L.tf("{name}: connected ({folder})", { name: driveRow.modelData.name, folder: driveRow.modelData.folder })
                                  : driveRow.modelData.name
                        }
                        QQC2.BusyIndicator { visible: cloud.busy === driveRow.modelData.service; running: visible }
                        QQC2.Button {
                            visible: !driveRow.modelData.configured
                            enabled: cloud.busy === ""
                            icon.name: "network-connect"
                            text: L.t("Sign in")
                            onClicked: cloud.connectDrive(driveRow.modelData.service)
                        }
                        QQC2.Button {
                            visible: driveRow.modelData.configured
                            enabled: cloud.busy === ""
                            icon.name: "folder-open"
                            text: L.t("Open")
                            onClicked: Qt.openUrlExternally("file://" + driveRow.modelData.folder)
                        }
                        QQC2.Button {
                            visible: driveRow.modelData.configured
                            enabled: cloud.busy === ""
                            icon.name: "network-disconnect"
                            text: L.t("Disconnect")
                            onClicked: cloud.disconnectDrive(driveRow.modelData.service)
                        }
                    }
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: cloud.infoText !== ""
                    type: Kirigami.MessageType.Information
                    text: cloud.infoText
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: cloud.errorText !== ""
                    type: Kirigami.MessageType.Error
                    text: cloud.errorText
                }
            }
        }

        // --- What to ask a password for -------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            enabled: accounts.isAdmin
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("When should the system ask for your password?") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("If a setting does not need a password, it runs from your account without asking. That is convenient, but anyone who sits down at your computer can do it too. We recommend keeping the password for disks, users and startup.")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: !accounts.isAdmin
                    wrapMode: Text.Wrap
                    color: Kirigami.Theme.neutralTextColor
                    text: L.t("Only an administrator account can turn this on.")
                }
                QQC2.ButtonGroup { id: presets }
                QQC2.RadioButton {
                    QQC2.ButtonGroup.group: presets
                    text: L.t("Ask for everything (the most secure)")
                    checked: accounts.preset === "all"
                    onClicked: accounts.applyPreset("all")
                }
                QQC2.RadioButton {
                    QQC2.ButtonGroup.group: presets
                    text: L.t("Ask only for risky things (disks, users, startup)")
                    checked: accounts.preset === "recommended"
                    onClicked: accounts.applyPreset("recommended")
                }
                QQC2.RadioButton {
                    id: customPreset
                    QQC2.ButtonGroup.group: presets
                    text: L.t("Custom, by topic")
                    checked: accounts.preset === "custom"
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.gridUnit
                    visible: customPreset.checked
                    spacing: Kirigami.Units.largeSpacing
                    Repeater {
                        model: accounts.topics
                        delegate: RowLayout {
                            id: topicRow
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: topicRow.modelData.name }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    opacity: 0.7
                                    font: Kirigami.Theme.smallFont
                                    text: topicRow.modelData.description
                                }
                            }
                            Kirigami.Icon {
                                visible: topicRow.modelData.risky && !topicRow.modelData.passwordNeeded
                                source: "data-warning"
                                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                                implicitHeight: Kirigami.Units.iconSizes.smallMedium
                            }
                            QQC2.Switch {
                                text: L.t("Password needed")
                                checked: topicRow.modelData.passwordNeeded
                                onToggled: accounts.setPasswordNeeded(topicRow.modelData.id, checked)
                            }
                        }
                    }
                }
            }
        }

        // --- Login and terminal ------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Kirigami.Heading { level: 3; text: L.t("Sign in automatically") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: L.t("When turned on, the computer starts straight to your desktop without a password. The store of saved passwords (e.g. Wi-Fi, browser) then asks for your password the first time it is used.")
                        }
                    }
                    QQC2.Switch {
                        checked: accounts.autologin
                        onToggled: accounts.setAutologin(checked)
                    }
                }
                Kirigami.Separator { Layout.fillWidth: true }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    enabled: accounts.isAdmin
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Kirigami.Heading { level: 3; text: L.t("Password in the terminal (sudo)") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: L.t("For advanced users: turn this off if you do not want the “sudo” command to ask for a password in the terminal.")
                        }
                    }
                    QQC2.Switch {
                        text: L.t("Password needed")
                        checked: !accounts.sudoWithoutPassword
                        onToggled: accounts.setSudoWithoutPassword(!checked)
                    }
                }
            }
        }

        // --- Which apps can use the camera, the microphone and the location (privacy.py) ---
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            Component.onCompleted: privacy.refresh()
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("App permissions") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Apps installed from Discover or Sloth Welcome that can use these. Many reach the camera only because they can use all devices, for example game controllers.")
                }
                RowLayout {
                    visible: privacy.busy
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.BusyIndicator { running: privacy.busy }
                    QQC2.Label { text: L.t("Checking…") }
                }
                Repeater {
                    model: privacy.busy ? [] : [
                        { icon: "camera-web", title: L.t("Camera"), apps: privacy.camera },
                        { icon: "audio-input-microphone", title: L.t("Microphone"), apps: privacy.microphone },
                        { icon: "find-location", title: L.t("Location"), apps: privacy.location }
                    ]
                    delegate: RowLayout {
                        id: permRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            Layout.alignment: Qt.AlignTop
                            source: permRow.modelData.icon
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { text: permRow.modelData.title; font.bold: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                opacity: 0.8
                                text: permRow.modelData.apps.length
                                      ? permRow.modelData.apps.map(a => a.name).join(", ")
                                      : L.t("No app can use it.")
                            }
                        }
                    }
                }
                QQC2.Button {
                    text: L.t("Change app permissions")
                    icon.name: "preferences-security"
                    onClicked: privacy.openSettings("")
                }
            }
        }
    }
}
