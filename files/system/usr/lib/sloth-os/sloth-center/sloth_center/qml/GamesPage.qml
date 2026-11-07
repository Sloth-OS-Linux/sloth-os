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
    // Fresh every time the page opens: a program removed (or marked) in Programs must not stay here
    Component.onCompleted: games.refresh()

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

        // --- "Will it run?": how well a game runs, from other players' reports (sloth_common.game_check) ---
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Will it run?") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("Type a game's name to see how well it runs on Sloth OS, based on other players' reports.")
                }
                Kirigami.SearchField {
                    id: checkField
                    Layout.fillWidth: true
                    enabled: games.checkState === "ready"
                    placeholderText: L.t("Game name")
                    // the list is searched at once (a few milliseconds): every key press shows the matches
                    onTextChanged: checkResults.model = games.checkSearch(text)
                }
                QQC2.Label {
                    visible: games.checkState !== "ready"
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: games.checkState === "loading" ? L.t("Downloading the game list…")
                        : L.t("The game list hasn't been downloaded yet. It downloads by itself when the computer is online.")
                }
                QQC2.Label {
                    visible: checkField.text.trim().length >= 2 && checkResults.count === 0 && games.checkState === "ready"
                    opacity: 0.7
                    text: L.t("No game found with that name.")
                }
                Repeater {
                    id: checkResults
                    model: []
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.smallSpacing
                        spacing: 0
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.smallSpacing
                            QQC2.Label { text: modelData.mark }
                            QQC2.Label { font.bold: true; text: modelData.badgeText }
                            QQC2.Label { text: "·"; opacity: 0.5 }
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: modelData.name }
                        }
                        Repeater {
                            model: modelData.lines
                            delegate: QQC2.Label {
                                required property string modelData
                                Layout.fillWidth: true
                                Layout.leftMargin: Kirigami.Units.gridUnit * 1.5
                                wrapMode: Text.Wrap
                                opacity: 0.8
                                text: modelData
                            }
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.5
                    font: Kirigami.Theme.smallFont
                    text: L.t("Data: ProtonDB (ODbL) and AreWeAntiCheatYet (MIT), updated monthly.")
                }
            }
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

        // --- Game saves: an hourly backup of every game's saves (game_saves.py, Ludusavi) ------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    Layout.fillWidth: true
                    Kirigami.Heading { level: 3; Layout.fillWidth: true; text: L.t("Game saves") }
                    QQC2.Switch {
                        visible: gameSaves.installed
                        checked: gameSaves.enabled
                        onToggled: {
                            if (checked) gameSaves.turnOn(); else gameSaves.turnOff();
                            checked = Qt.binding(() => gameSaves.enabled)
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Many games keep their saves only on this computer, without a cloud copy. Sloth OS can back them up every hour, for Steam, Heroic and your Windows games, and put an earlier save back if a game breaks it.")
                }
                QQC2.Button {
                    visible: !gameSaves.installed || !gameSaves.enabled
                    icon.name: "document-save"
                    text: gameSaves.installed ? L.t("Turn on") : L.t("Turn on (installs Ludusavi, 43 MB)")
                    onClicked: gameSaves.turnOn()
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: !gameSaves.installed && gameSaves.enabled
                    opacity: 0.8
                    text: L.t("Click Install in Discover. The backup starts by itself when Ludusavi is installed.")
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: gameSaves.installed && gameSaves.enabled
                    QQC2.Label { Layout.fillWidth: true; opacity: 0.8; text: gameSaves.lastBackup }
                    QQC2.Button {
                        icon.name: "document-save"
                        text: L.t("Back up now")
                        enabled: gameSaves.busy === "" || gameSaves.busy === "list"
                        onClicked: gameSaves.backupNow()
                    }
                    QQC2.Button {
                        icon.name: "folder-open"
                        text: L.t("Open folder")
                        onClicked: gameSaves.openFolder()
                    }
                }
                QQC2.ProgressBar {
                    Layout.fillWidth: true
                    visible: gameSaves.busy === "backup" || gameSaves.busy === "restore"
                    indeterminate: true
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    type: Kirigami.MessageType.Error
                    visible: gameSaves.errorText !== ""
                    text: gameSaves.errorText
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    type: Kirigami.MessageType.Positive
                    visible: gameSaves.infoText !== "" && gameSaves.busy === ""
                    text: gameSaves.infoText
                }
                Repeater {
                    model: gameSaves.enabled ? gameSaves.saves : []
                    delegate: RowLayout {
                        id: saveRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon { source: "input-gamepad"; implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: implicitWidth }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: saveRow.modelData.name }
                            QQC2.Label {
                                Layout.fillWidth: true
                                opacity: 0.7
                                text: [saveRow.modelData.when, saveRow.modelData.size].filter(t => t !== "").join(" · ")
                            }
                        }
                        QQC2.Button {
                            icon.name: "edit-undo"
                            text: L.t("Restore")
                            enabled: gameSaves.busy === "" || gameSaves.busy === "list"
                            onClicked: { confirmRestore.game = saveRow.modelData.name; confirmRestore.open(); }
                        }
                    }
                }
            }
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
            explanation: L.t("Your Steam games and Windows games appear here. Is a Windows game missing? Mark it as a game in Programs.")
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
                            // "Will it run?" for the installed game: the mark and the verdict
                            QQC2.Label {
                                visible: !!gameCard.modelData.check && !!gameCard.modelData.check.badgeText
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: visible ? gameCard.modelData.check.mark + " " + gameCard.modelData.check.badgeText : ""
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

    Kirigami.PromptDialog {
        id: confirmRestore
        property string game: ""
        title: L.tf("Put back the saved game of {game}?", { game: game })
        subtitle: L.t("The save on this computer is replaced by the newest backup. Close the game first. If you change your mind, File backup still has the save from before.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Restore")
                icon.name: "edit-undo"
                onTriggered: { gameSaves.restore(confirmRestore.game); confirmRestore.close(); }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirmRestore.close()
            }
        ]
    }

    // Closing Steam takes a few seconds
    Timer {
        id: refreshLater
        interval: 5000
        onTriggered: games.refresh()
    }
}
