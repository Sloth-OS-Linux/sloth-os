// Telepített Windows-programok: lista, méret, eltávolítás.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Windows-programok")

    actions: [
        Kirigami.Action {
            text: L.t("Frissítés")
            icon.name: "view-refresh"
            onTriggered: winprograms.refresh()
        }
    ]

    ListView {
        id: list
        model: winprograms.programs
        spacing: Kirigami.Units.smallSpacing

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 4
            visible: list.count === 0
            icon.name: "application-x-ms-dos-executable"
            text: L.t("Még nincs telepített Windows-program")
            explanation: L.t("Kattints duplán egy .exe vagy .msi fájlra (például egy letöltött telepítőre), és itt fog megjelenni.")
        }

        delegate: Kirigami.AbstractCard {
            id: card
            required property var modelData
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
                            const names = card.modelData.entries.map(e => e.name);
                            const parts = [];
                            if (card.modelData.size !== "") parts.push(card.modelData.size);
                            parts.push(names.length > 0 ? L.tf("A Start menüben: {names}", { names: names.join(", ") }) : L.t("Nincs a Start menüben"));
                            return parts.join(" · ");
                        }
                    }
                }
                QQC2.Button {
                    text: L.t("Start menü")
                    icon.name: "kickoff"
                    onClicked: winprograms.editShortcuts(card.modelData.slug)
                }
                QQC2.Button {
                    text: L.t("Eltávolítás")
                    icon.name: "edit-delete"
                    onClicked: {
                        confirm.target = card.modelData;
                        confirm.open();
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirm
        property var target: null
        title: target ? L.tf("Eltávolítod: {name}?", { name: target.name }) : ""
        subtitle: L.t("A program és minden hozzá tartozó fájl törlődik (a mentésekkel és beállításokkal együtt). Ezt nem lehet visszavonni.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Eltávolítás")
                icon.name: "edit-delete"
                onTriggered: { winprograms.remove(confirm.target.slug); confirm.close(); }
            },
            Kirigami.Action {
                text: L.t("Mégse")
                icon.name: "dialog-cancel"
                onTriggered: confirm.close()
            }
        ]
    }
}
