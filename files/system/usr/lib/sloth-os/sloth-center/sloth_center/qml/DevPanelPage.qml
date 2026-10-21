// Developer panel: developing Sloth OS without a terminal (repository, builds, signing key, trying out).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Developer panel")

    actions: [
        Kirigami.Action {
            text: L.t("Refresh")
            icon.name: "view-refresh"
            enabled: devpanel.connected
            onTriggered: devpanel.refresh()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: devpanel.errorText !== ""
            text: devpanel.errorText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Information
            visible: devpanel.message !== ""
            text: devpanel.message
        }
        QQC2.ProgressBar {
            Layout.fillWidth: true
            visible: devpanel.busy
            indeterminate: true
        }

        // --- Connection ------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Connection to GitHub") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: devpanel.connected
                          ? L.tf("Connected: {repo}", { repo: devpanel.repo })
                          : L.t("Enter the repository and a GitHub token. The button creates the token on GitHub with the permissions needed (repository, builds, reading packages); copy it here from there. It stays in the password store and can be removed from this computer at any time.")
                }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.TextField {
                        id: repoField
                        Layout.fillWidth: true
                        text: devpanel.repo
                        placeholderText: "Sloth-OS-Linux/sloth-os"
                    }
                    QQC2.TextField {
                        id: tokenField
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: devpanel.connected ? L.t("Token (only if you want to replace it)") : L.t("Token")
                    }
                }
                RowLayout {
                    QQC2.Button {
                        text: L.t("Create a token on GitHub")
                        icon.name: "internet-services"
                        onClicked: devpanel.createToken()
                    }
                    QQC2.Button {
                        highlighted: !devpanel.connected
                        enabled: !devpanel.busy
                        text: L.t("Connect")
                        icon.name: "network-connect"
                        onClicked: { devpanel.connectRepo(repoField.text, tokenField.text); tokenField.text = ""; }
                    }
                    QQC2.Button {
                        visible: devpanel.connected
                        text: L.t("Remove token")
                        icon.name: "edit-delete"
                        onClicked: devpanel.disconnect()
                    }
                }
            }
        }

        // --- Buildek ----------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: devpanel.connected
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                RowLayout {
                    Layout.fillWidth: true
                    Kirigami.Heading { level: 3; text: L.t("Builds"); Layout.fillWidth: true }
                    QQC2.Label {
                        visible: devpanel.minutes >= 0
                        opacity: 0.7
                        text: L.tf("This month: {minutes} minutes", { minutes: devpanel.minutes })
                    }
                }
                RowLayout {
                    QQC2.Button {
                        enabled: !devpanel.busy
                        text: L.t("Start image build")
                        icon.name: "run-build"
                        onClicked: devpanel.startBuild("image")
                    }
                    QQC2.Button {
                        enabled: !devpanel.busy
                        text: L.t("Start ISO build")
                        icon.name: "media-optical"
                        onClicked: devpanel.startBuild("iso")
                    }
                }
                Repeater {
                    model: devpanel.runs
                    delegate: RowLayout {
                        id: runRow
                        required property var modelData
                        Layout.fillWidth: true
                        Kirigami.Icon {
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                            source: runRow.modelData.state === "ok" ? "emblem-success"
                                  : runRow.modelData.state === "running" ? "chronometer"
                                  : runRow.modelData.state === "cancelled" ? "emblem-pause" : "emblem-error"
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: runRow.modelData.when + " · " + runRow.modelData.name + " · " + runRow.modelData.title
                        }
                        QQC2.Button {
                            visible: runRow.modelData.state === "ok" && runRow.modelData.name === "bluebuild"
                            enabled: !devpanel.busy
                            text: L.t("Switch to this")
                            icon.name: "go-jump"
                            QQC2.ToolTip.visible: hovered
                            QQC2.ToolTip.text: L.t("This computer will start from this build after the next restart. The current version stays in the boot menu.")
                            onClicked: devpanel.switchTo(devpanel.tagFor(runRow.modelData.sha))
                        }
                        QQC2.ToolButton {
                            icon.name: "internet-services"
                            text: L.t("Open on GitHub")
                            display: QQC2.AbstractButton.IconOnly
                            QQC2.ToolTip.visible: hovered
                            QQC2.ToolTip.text: text
                            onClicked: devpanel.openUrl(runRow.modelData.url)
                        }
                    }
                }
            }
        }

        // --- Signing key ------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: devpanel.connected
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Signing key") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: !devpanel.secretKnown ? ""
                          : devpanel.hasSecret ? L.t("Set up: builds are signed, and computers check the signature of updates.")
                          : L.t("Not set up yet: builds can't be completed without a signature.")
                }
                QQC2.Button {
                    enabled: !devpanel.busy
                    text: devpanel.hasSecret ? L.t("New key pair…") : L.t("Create key pair")
                    icon.name: "document-encrypt"
                    onClicked: devpanel.hasSecret ? keyConfirm.open() : devpanel.createSigningKey()
                }
            }
        }

        // --- Trying out --------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: devpanel.connected
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Trying it out") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.tf("This computer is running: {image}", { image: devpanel.currentImage !== "" ? devpanel.currentImage : "?" })
                }
                RowLayout {
                    QQC2.Button {
                        visible: devpanel.privateRepo
                        enabled: !devpanel.busy
                        text: L.t("Sign in to the package registry")
                        icon.name: "unlock"
                        QQC2.ToolTip.visible: hovered
                        QQC2.ToolTip.text: L.t("Needed for a private repository: without it, the computer can't download updates or builds.")
                        onClicked: devpanel.registryLogin()
                    }
                    QQC2.Button {
                        enabled: !devpanel.busy
                        text: L.t("Back to the latest")
                        icon.name: "go-home"
                        onClicked: devpanel.switchTo("latest")
                    }
                    QQC2.Button {
                        text: L.t("Virtual machine")
                        icon.name: "computer"
                        onClicked: devpanel.openBoxes()
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: keyConfirm
        title: L.t("New signing key?")
        subtitle: L.t("Computers already installed accept updates signed with the old key. After a new key, their updates stop until the new public key (cosign.pub) reaches them in an update that was still signed with the old key. Only replace it if the old key was lost or leaked.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("New key pair")
                icon.name: "document-encrypt"
                onTriggered: { devpanel.createSigningKey(); keyConfirm.close(); }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: keyConfirm.close()
            }
        ]
    }
}
