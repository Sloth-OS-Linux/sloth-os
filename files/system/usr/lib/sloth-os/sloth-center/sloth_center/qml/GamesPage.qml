// Játékok: játékonkénti beállítások (FPS-kijelző, teljesítmény mód, felskálázás) a Steames
// játékokhoz és a Windows-programokhoz. A technikai részletek (Proton, Wine) nem látszanak.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Games")

    actions: [
        Kirigami.Action {
            text: L.t("Refresh")
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
            text: L.t("Here you can choose for each game whether to show the FPS, give the game more power, and upscale it. The change takes effect the next time the game starts.")
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
            text: L.t("Steam is running. Close it first to change the settings of Steam games.")
            actions: [
                Kirigami.Action {
                    text: L.t("Close Steam")
                    icon.name: "application-exit"
                    onTriggered: { games.closeSteam(); refreshLater.start(); }
                }
            ]
        }
        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: games.games.length === 0
            icon.name: "input-gamepad"
            text: L.t("No games installed yet")
            explanation: L.t("Games installed from Steam and Windows programs appear here.")
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
                                text: gameCard.modelData.source === "steam" ? L.t("Steam") : L.t("Windows program")
                            }
                        }
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        enabled: !gameCard.locked
                        columns: 2
                        columnSpacing: Kirigami.Units.largeSpacing
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: L.t("Show FPS and performance while playing") }
                        QQC2.Switch {
                            checked: gameCard.modelData.fps
                            onToggled: games.setOption(gameCard.modelData.id, "fps", checked)
                        }
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: L.t("Performance mode (the computer focuses on the game)") }
                        QQC2.Switch {
                            checked: gameCard.modelData.performance
                            onToggled: games.setOption(gameCard.modelData.id, "performance", checked)
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: L.t("Upscaling: the game runs at a lower resolution and is sharpened and enlarged. More FPS, slightly less sharp image.")
                        }
                        QQC2.ComboBox {
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 11
                            model: [
                                { value: "off", text: L.t("Off") },
                                { value: "quality", text: L.t("Quality") },
                                { value: "balanced", text: L.t("Balanced") },
                                { value: "performance", text: L.t("Performance") }
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
