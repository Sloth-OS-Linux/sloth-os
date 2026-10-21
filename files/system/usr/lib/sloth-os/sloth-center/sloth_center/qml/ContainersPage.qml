// Fejlesztői környezetek: más Linux-rendszerek dobozban (Distrobox).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Developer environments")
    property string selectedBox: ""

    actions: [
        Kirigami.Action {
            text: L.t("Refresh")
            icon.name: "view-refresh"
            onTriggered: containers.refresh()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("A “box” is another Linux system (for example Ubuntu) running inside Sloth OS. It's useful if a program was made only for that system. You can also add apps installed in the box to the Start menu.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: containers.errorText !== ""
            text: containers.errorText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: containers.infoText !== "" && !containers.busy
            text: containers.infoText
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: containers.busy
            QQC2.Label { text: containers.statusText }
            QQC2.ProgressBar { Layout.fillWidth: true; indeterminate: true }
        }

        // --- Meglévő dobozok -----------------------------------------------------------
        Repeater {
            model: containers.boxes
            delegate: Kirigami.AbstractCard {
                id: boxCard
                required property var modelData
                Layout.fillWidth: true
                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.largeSpacing
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "utilities-terminal"
                            implicitWidth: Kirigami.Units.iconSizes.large
                            implicitHeight: Kirigami.Units.iconSizes.large
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Kirigami.Heading { level: 3; text: boxCard.modelData.name }
                            QQC2.Label { opacity: 0.7; text: boxCard.modelData.distro + (boxCard.modelData.running ? " · " + L.t("running") : "") }
                        }
                        QQC2.Button {
                            icon.name: "view-list-icons"
                            text: page.selectedBox === boxCard.modelData.name ? L.t("Close") : L.t("Manage")
                            onClicked: {
                                if (page.selectedBox === boxCard.modelData.name) {
                                    page.selectedBox = "";
                                } else {
                                    page.selectedBox = boxCard.modelData.name;
                                    containers.listApps(boxCard.modelData.name);
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: page.selectedBox === boxCard.modelData.name
                        spacing: Kirigami.Units.largeSpacing

                        RowLayout {
                            Layout.fillWidth: true
                            QQC2.TextField {
                                id: pkgField
                                Layout.fillWidth: true
                                placeholderText: L.t("Install a program into the box (package name, e.g. gimp)")
                                onAccepted: installBtn.clicked()
                            }
                            QQC2.Button {
                                id: installBtn
                                enabled: pkgField.text.trim() !== "" && !containers.busy
                                icon.name: "download"
                                text: L.t("Install")
                                onClicked: { containers.installPackage(boxCard.modelData.name, pkgField.text); pkgField.text = ""; }
                            }
                        }

                        Kirigami.Heading { level: 4; text: L.t("Apps in the Start menu") }
                        QQC2.Label {
                            visible: containers.apps.length === 0
                            opacity: 0.7
                            text: L.t("There's no graphical app in this box yet.")
                        }
                        Repeater {
                            model: containers.apps
                            delegate: QQC2.CheckDelegate {
                                required property var modelData
                                Layout.fillWidth: true
                                text: modelData.name
                                checked: modelData.exported
                                enabled: !containers.busy
                                onToggled: containers.setExported(modelData.box, modelData.id, checked)
                            }
                        }

                        RowLayout {
                            QQC2.Button {
                                icon.name: "utilities-terminal"
                                text: L.t("Open command line")
                                onClicked: containers.openTerminal(boxCard.modelData.name)
                            }
                            Item { Layout.fillWidth: true }
                            QQC2.Button {
                                icon.name: "edit-delete"
                                text: L.t("Delete box")
                                enabled: !containers.busy
                                onClicked: { confirmRemove.target = boxCard.modelData.name; confirmRemove.open(); }
                            }
                        }
                    }
                }
            }
        }

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: containers.boxes.length === 0 && !containers.busy
            icon.name: "utilities-terminal"
            text: L.t("You don't have a box yet")
        }

        // --- Új doboz ------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("New box") }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.ComboBox {
                        id: distroBox
                        model: containers.distros
                        textRole: "name"
                        valueRole: "id"
                        onActivated: nameField.text = currentValue + "-doboz"
                        Component.onCompleted: nameField.text = currentValue + "-doboz"
                    }
                    QQC2.TextField {
                        id: nameField
                        Layout.fillWidth: true
                        placeholderText: L.t("Box name")
                    }
                    QQC2.Button {
                        enabled: !containers.busy && nameField.text.trim() !== ""
                        highlighted: true
                        icon.name: "list-add"
                        text: L.t("Create")
                        onClicked: containers.create(distroBox.currentValue, nameField.text)
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("Creating it the first time can take a few minutes, depending on your connection.")
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirmRemove
        property string target: ""
        title: L.tf("Delete the box “{name}”?", { name: target })
        subtitle: L.t("Programs installed in the box will be deleted. The files in your own folder are kept.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Delete")
                icon.name: "edit-delete"
                onTriggered: { containers.remove(confirmRemove.target); page.selectedBox = ""; confirmRemove.close(); }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirmRemove.close()
            }
        ]
    }
}
