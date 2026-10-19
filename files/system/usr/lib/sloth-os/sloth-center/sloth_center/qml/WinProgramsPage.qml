// Telepített Windows-programok: lista, indítás, fájlok, javítás, áthelyezés, eltávolítás,
// a telepítési hely, és a Steamhez hozzáadott programok átvétele.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Windows-programok")

    actions: [
        Kirigami.Action {
            text: L.t("Telepítés…")
            icon.name: "download"
            onTriggered: installDialog.open()
        },
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

            // Hová települnek a programok
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
                            text: L.tf("Programok helye: {path}", { path: winprograms.location })
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.7
                            text: L.t("Minden program saját mappát kap, a Fájlok gombbal megnyitható. Ha máshová (például egy másik meghajtóra) szeretnéd tenni őket, válassz új helyet: az új programok oda kerülnek, a meglévők egyenként áthelyezhetők.")
                        }
                    }
                    QQC2.Button {
                        text: L.t("Módosítás…")
                        icon.name: "folder-open"
                        onClicked: locationDialog.open()
                    }
                }
            }

            // Közös tudás: a bevált beállítások névtelen megosztása (alapból kikapcsolva)
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
                        Kirigami.Heading { level: 3; text: L.t("Tapasztalatok megosztása"); Layout.fillWidth: true }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.7
                            text: L.t("Ha egy program nálad elindul, névtelenül megosztjuk, melyik beállítással ment, így más Sloth OS-es gépeken is elsőre elindul. Csak a beállítás és a videókártya gyártója kerül át: se a neved, se a fájljaid, se a program neve.")
                        }
                    }
                    QQC2.Switch {
                        checked: winprograms.sharing
                        onToggled: winprograms.setSharing(checked)
                    }
                }
            }

            // A Steamhez kézzel hozzáadott Windows-programok átvétele
            Kirigami.AbstractCard {
                Layout.fillWidth: true
                visible: winprograms.steamPrograms.length > 0
                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing
                    RowLayout {
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "steam"
                            fallback: "applications-games"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Kirigami.Heading { level: 3; text: L.t("A Steamhez hozzáadott programok"); Layout.fillWidth: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                opacity: 0.7
                                text: L.t("Ezeket a Steamben adtad hozzá. Felveheted őket ide is, újratelepítés nélkül. „A Steamen keresztül”: a Steam indítja, ahogy eddig. „Átvétel”: saját másolatot kap, és a Steam nélkül is indul. A Steamben egyik esetben sem változik semmi.")
                            }
                        }
                    }
                    Repeater {
                        model: winprograms.steamPrograms
                        delegate: RowLayout {
                            id: steamRow
                            required property var modelData
                            Layout.fillWidth: true
                            QQC2.Label {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: steamRow.modelData.name
                            }
                            QQC2.Button {
                                text: L.t("A Steamen keresztül")
                                enabled: !winprograms.busy
                                onClicked: winprograms.importSteam(steamRow.modelData.appid, false)
                            }
                            QQC2.Button {
                                text: L.t("Átvétel")
                                enabled: steamRow.modelData.canAdopt && !winprograms.busy
                                onClicked: winprograms.importSteam(steamRow.modelData.appid, true)
                                QQC2.ToolTip.visible: hovered && !steamRow.modelData.canAdopt
                                QQC2.ToolTip.text: L.t("Ennek a programnak nincs saját környezete a Steamben, ezért csak a Steamen keresztül vehető fel.")
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
            text: L.t("Még nincs telepített Windows-program")
            explanation: L.t("Kattints duplán egy .exe vagy .msi fájlra (például egy letöltött telepítőre), vagy válaszd a Telepítés… gombot, és itt fog megjelenni.")
        }

        delegate: Kirigami.AbstractCard {
            id: card
            required property var modelData
            readonly property bool isSteam: card.modelData.kind === "steam"
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
                            if (card.isSteam)
                                parts.push(L.t("A Steamen keresztül"));
                            else if (card.modelData.size !== "")
                                parts.push(card.modelData.size);
                            if (card.modelData.publisher !== "")
                                parts.push(card.modelData.publisher);
                            const names = card.modelData.entries.map(e => e.name);
                            parts.push(names.length > 0 ? L.tf("A Start menüben: {names}", { names: names.join(", ") }) : L.t("Nincs a Start menüben"));
                            return parts.join(" · ");
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: !card.isSteam
                        opacity: 0.5
                        elide: Text.ElideMiddle
                        font: Kirigami.Theme.smallFont
                        text: card.modelData.folder
                    }
                }
                QQC2.Button {
                    visible: !card.modelData.shared
                    highlighted: true
                    text: L.t("Indítás")
                    icon.name: "media-playback-start"
                    onClicked: winprograms.launch(card.modelData.id)
                }
                QQC2.Button {
                    visible: !card.isSteam
                    text: L.t("Fájlok")
                    icon.name: "folder-open"
                    onClicked: winprograms.openFolder(card.modelData.id)
                }
                QQC2.ToolButton {
                    icon.name: "overflow-menu"
                    text: L.t("Továbbiak")
                    display: QQC2.AbstractButton.IconOnly
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.text: text
                    onClicked: moreMenu.popup()
                    QQC2.Menu {
                        id: moreMenu
                        QQC2.MenuItem {
                            visible: !card.isSteam
                            height: visible ? implicitHeight : 0
                            text: L.t("Start menü…")
                            icon.name: "kickoff"
                            onTriggered: winprograms.editShortcuts(card.modelData.id)
                        }
                        QQC2.MenuItem {
                            visible: !card.isSteam && !card.modelData.shared
                            height: visible ? implicitHeight : 0
                            text: L.t("Javítás")
                            icon.name: "tools-wizard"
                            onTriggered: winprograms.repair(card.modelData.id)
                        }
                        QQC2.MenuItem {
                            visible: card.modelData.canReinstall
                            height: visible ? implicitHeight : 0
                            text: L.t("Újratelepítés")
                            icon.name: "view-refresh"
                            onTriggered: winprograms.reinstall(card.modelData.id)
                        }
                        QQC2.MenuItem {
                            visible: card.modelData.canMove
                            height: visible ? implicitHeight : 0
                            text: L.tf("Áthelyezés ide: {path}", { path: winprograms.location })
                            icon.name: "folder-move"
                            enabled: !winprograms.busy
                            onTriggered: winprograms.move(card.modelData.id)
                        }
                        QQC2.MenuSeparator {}
                        QQC2.MenuItem {
                            text: L.t("Eltávolítás")
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
        title: target ? L.tf("Eltávolítod: {name}?", { name: target.name }) : ""
        subtitle: target && target.kind === "steam"
                  ? L.t("Csak innen és a Start menüből tűnik el; a Steamben minden marad.")
                  : L.t("A program és minden hozzá tartozó fájl törlődik (a mentésekkel és beállításokkal együtt). Ezt nem lehet visszavonni.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Eltávolítás")
                icon.name: "edit-delete"
                onTriggered: { winprograms.remove(confirm.target.id); confirm.close(); }
            },
            Kirigami.Action {
                text: L.t("Mégse")
                icon.name: "dialog-cancel"
                onTriggered: confirm.close()
            }
        ]
    }

    FileDialog {
        id: installDialog
        title: L.t("Melyik programot telepíted?")
        currentFolder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
        nameFilters: [L.t("Windows-programok") + " (*.exe *.msi *.EXE *.MSI)"]
        onAccepted: winprograms.install(selectedFile.toString())
    }

    FolderDialog {
        id: locationDialog
        title: L.t("Hová települjenek az új programok?")
        onAccepted: winprograms.setLocation(selectedFolder.toString())
    }
}
