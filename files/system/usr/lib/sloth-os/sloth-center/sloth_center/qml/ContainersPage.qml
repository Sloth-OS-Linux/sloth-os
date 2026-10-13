// Fejlesztői környezetek: más Linux-rendszerek dobozban (Distrobox).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: "Fejlesztői környezetek"
    property string selectedBox: ""

    actions: [
        Kirigami.Action {
            text: "Frissítés"
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
            text: "Egy „doboz” egy másik Linux-rendszer (például Ubuntu), ami a Sloth OS-en belül fut. Akkor hasznos, ha egy program csak arra a rendszerre készült. A dobozban telepített appokat a Start menübe is kiteheted."
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
                            QQC2.Label { opacity: 0.7; text: boxCard.modelData.distro + (boxCard.modelData.running ? " · fut" : "") }
                        }
                        QQC2.Button {
                            icon.name: "view-list-icons"
                            text: page.selectedBox === boxCard.modelData.name ? "Bezárás" : "Kezelés"
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
                                placeholderText: "Program telepítése a dobozba (csomagnév, pl. gimp)"
                                onAccepted: installBtn.clicked()
                            }
                            QQC2.Button {
                                id: installBtn
                                enabled: pkgField.text.trim() !== "" && !containers.busy
                                icon.name: "download"
                                text: "Telepítés"
                                onClicked: { containers.installPackage(boxCard.modelData.name, pkgField.text); pkgField.text = ""; }
                            }
                        }

                        Kirigami.Heading { level: 4; text: "Appok a Start menübe" }
                        QQC2.Label {
                            visible: containers.apps.length === 0
                            opacity: 0.7
                            text: "Ebben a dobozban még nincs grafikus app."
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
                                text: "Parancssor megnyitása"
                                onClicked: containers.openTerminal(boxCard.modelData.name)
                            }
                            Item { Layout.fillWidth: true }
                            QQC2.Button {
                                icon.name: "edit-delete"
                                text: "Doboz törlése"
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
            text: "Még nincs dobozod"
        }

        // --- Új doboz ------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: "Új doboz" }
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
                        placeholderText: "A doboz neve"
                    }
                    QQC2.Button {
                        enabled: !containers.busy && nameField.text.trim() !== ""
                        highlighted: true
                        icon.name: "list-add"
                        text: "Létrehozás"
                        onClicked: containers.create(distroBox.currentValue, nameField.text)
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: "Az első létrehozás a netkapcsolattól függően néhány percig tarthat."
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirmRemove
        property string target: ""
        title: "Törlöd a(z) „" + target + "” dobozt?"
        subtitle: "A dobozban telepített programok törlődnek. A saját mappádban lévő fájljaid megmaradnak."
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: "Törlés"
                icon.name: "edit-delete"
                onTriggered: { containers.remove(confirmRemove.target); page.selectedBox = ""; confirmRemove.close(); }
            },
            Kirigami.Action {
                text: "Mégse"
                icon.name: "dialog-cancel"
                onTriggered: confirmRemove.close()
            }
        ]
    }
}
