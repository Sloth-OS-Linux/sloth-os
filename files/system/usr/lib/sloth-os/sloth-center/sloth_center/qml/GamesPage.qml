// Játékok: játékonkénti beállítások (FPS-kijelző, teljesítmény mód, felskálázás) a Steames
// játékokhoz és a Windows-programokhoz. A technikai részletek (Proton, Wine) nem látszanak.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Játékok")

    actions: [
        Kirigami.Action {
            text: L.t("Frissítés")
            icon.name: "view-refresh"
            onTriggered: games.refresh()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("Itt minden játékhoz külön beállíthatod, hogy mutassa-e az FPS-t, kapjon-e több erőt a gép, és felskálázzon-e. A változás a játék következő indításakor lép életbe.")
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: games.errorText !== ""
            text: games.errorText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: games.infoText !== ""
            text: games.infoText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Information
            visible: games.steamRunning
            text: L.t("A Steam most fut. A Steames játékok beállításához előbb zárd be.")
            actions: [
                Kirigami.Action {
                    text: L.t("Steam bezárása")
                    icon.name: "application-exit"
                    onTriggered: { games.closeSteam(); refreshLater.start(); }
                }
            ]
        }
        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: games.games.length === 0
            icon.name: "input-gamepad"
            text: L.t("Még nincs telepített játék")
            explanation: L.t("A Steamből telepített játékok és a Windows-programok itt jelennek meg.")
        }

        Repeater {
            model: games.games
            delegate: Kirigami.AbstractCard {
                id: gameCard
                required property var modelData
                readonly property bool locked: gameCard.modelData.source === "steam" && games.steamRunning
                Layout.fillWidth: true
                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.largeSpacing
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: gameCard.modelData.source === "steam" ? "steam" : "application-x-ms-dos-executable"
                            fallback: "input-gamepad"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Kirigami.Heading { Layout.fillWidth: true; level: 3; elide: Text.ElideRight; text: gameCard.modelData.name }
                            QQC2.Label {
                                opacity: 0.7
                                text: gameCard.modelData.source === "steam" ? L.t("Steam") : L.t("Windows-program")
                            }
                        }
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        enabled: !gameCard.locked
                        columns: 2
                        columnSpacing: Kirigami.Units.largeSpacing
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: L.t("FPS és teljesítmény kijelzése játék közben") }
                        QQC2.Switch {
                            checked: gameCard.modelData.fps
                            onToggled: games.setOption(gameCard.modelData.id, "fps", checked)
                        }
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: L.t("Teljesítmény mód (a gép a játékra koncentrál)") }
                        QQC2.Switch {
                            checked: gameCard.modelData.performance
                            onToggled: games.setOption(gameCard.modelData.id, "performance", checked)
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: L.t("Felskálázás: a játék kisebb felbontásban fut, és élesítve nagyítjuk fel. Több FPS, kicsit kevésbé éles kép.")
                        }
                        QQC2.ComboBox {
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 11
                            model: [
                                { value: "off", text: L.t("Ki") },
                                { value: "quality", text: L.t("Minőség") },
                                { value: "balanced", text: L.t("Kiegyensúlyozott") },
                                { value: "performance", text: L.t("Teljesítmény") }
                            ]
                            textRole: "text"
                            valueRole: "value"
                            // nem indexOfValue(): az a modell betöltése előtt fut, és -1-et ad (üres mező)
                            currentIndex: Math.max(0, model.findIndex(m => m.value === gameCard.modelData.upscale))
                            onActivated: games.setOption(gameCard.modelData.id, "upscale", currentValue)
                        }
                    }
                }
            }
        }
    }

    // A Steam bezárása eltart pár másodpercig
    Timer {
        id: refreshLater
        interval: 5000
        onTriggered: games.refresh()
    }
}
