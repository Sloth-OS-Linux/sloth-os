// Games: per-game settings (FPS display, performance mode, upscaling) for Steam
// games and Windows programs. The technical details (Proton, Wine) are not visible.
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
                property var moveTargets: []  // filled by "Move to another drive…": the choices shown
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
                                Layout.fillWidth: true
                                opacity: 0.7
                                elide: Text.ElideRight
                                // "Steam · Main drive · 64 GB"
                                text: [gameCard.modelData.source === "steam" ? L.t("Steam") : L.t("Windows program"),
                                       gameCard.modelData.place || "", gameCard.modelData.size || ""]
                                      .filter(s => s !== "").join(" · ")
                            }
                        }
                        // Moving a Steam game to another drive (sloth_common.apps.steam_library)
                        QQC2.Button {
                            visible: gameCard.modelData.movable === true && games.movingId !== gameCard.modelData.id
                                     && gameCard.moveTargets.length === 0
                            enabled: !games.steamRunning && games.movingId === ""
                            text: L.t("Move to another drive…")
                            icon.name: "folder-move"
                            onClicked: gameCard.moveTargets = games.moveTargets(gameCard.modelData.id)
                        }
                    }
                    // The drives it can go to, one button each
                    Flow {
                        visible: gameCard.moveTargets.length > 0
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        QQC2.Label {
                            height: implicitHeight
                            text: L.t("Move it to:")
                        }
                        Repeater {
                            model: gameCard.moveTargets
                            delegate: QQC2.Button {
                                required property var modelData
                                text: modelData.label + " (" + modelData.free + ")"
                                icon.name: "drive-harddisk"
                                onClicked: {
                                    games.moveGame(gameCard.modelData.id, modelData.path)
                                    gameCard.moveTargets = []
                                }
                            }
                        }
                        QQC2.Button {
                            text: L.t("Cancel")
                            onClicked: gameCard.moveTargets = []
                        }
                    }
                    // While the game is moving: it may take a while for a big game
                    RowLayout {
                        visible: games.movingId === gameCard.modelData.id
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.BusyIndicator { running: parent.visible }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: L.t("Moving the game… With a big game this can take a while. Don't start Steam until it is done.")
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
                            // not indexOfValue(): that runs before the model is loaded, and returns -1 (empty field)
                            currentIndex: Math.max(0, model.findIndex(m => m.value === gameCard.modelData.upscale))
                            onActivated: games.setOption(gameCard.modelData.id, "upscale", currentValue)
                        }
                    }
                }
            }
        }
    }

    // Closing Steam takes a few seconds
    Timer {
        id: refreshLater
        interval: 5000
        onTriggered: games.refresh()
    }
}
