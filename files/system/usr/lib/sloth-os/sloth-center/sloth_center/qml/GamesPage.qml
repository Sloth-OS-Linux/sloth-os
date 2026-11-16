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
    Component.onCompleted: {
        games.refresh();
        // sloth-center --page games --game <id>: the game's settings at once (the "closed right after it started"
        // notification)
        if (typeof startGame !== "undefined" && startGame !== "" && games.games.some(g => g.id === startGame)) {
            gameDialog.gameId = startGame;
            gameDialog.open();
        }
    }

    function play(game) {
        if (game.source === "windows")
            winprograms.launch(game.id.slice(4));
        else
            games.play(game.id);
    }

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

        // --- The library: every game with its cover; a click starts it, the gear opens its settings -------------
        Flow {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Repeater {
                model: games.games
                delegate: QQC2.ItemDelegate {
                    id: tile
                    required property var modelData
                    readonly property string sourceText: ({
                        steam: "Steam", epic: "Epic Games", gog: "GOG", amazon: "Amazon Games",
                        windows: L.t("Windows program"), flatpak: L.t("App") })[modelData.source] || ""
                    width: Kirigami.Units.gridUnit * 9
                    padding: Kirigami.Units.smallSpacing
                    onClicked: page.play(modelData)
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.text: L.tf("Start {game}", { game: modelData.name })
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing
                        // the cover (2:3, as stores show them); without one: the icon and the name
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: width * 1.5
                            radius: Kirigami.Units.cornerRadius
                            color: Kirigami.Theme.alternateBackgroundColor
                            border.color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
                            clip: true
                            Image {
                                id: cover
                                anchors.fill: parent
                                anchors.margins: 1
                                visible: status === Image.Ready
                                source: tile.modelData.cover ? "file://" + tile.modelData.cover : ""
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                sourceSize.width: 360
                            }
                            ColumnLayout {
                                anchors.centerIn: parent
                                width: parent.width - Kirigami.Units.gridUnit
                                visible: !cover.visible
                                spacing: Kirigami.Units.smallSpacing
                                Kirigami.Icon {
                                    Layout.alignment: Qt.AlignHCenter
                                    source: tile.modelData.icon || (tile.modelData.source === "steam" ? "steam"
                                            : tile.modelData.source === "windows" ? "application-x-ms-dos-executable"
                                            : ["epic", "gog", "amazon"].includes(tile.modelData.source)
                                              ? "com.heroicgameslauncher.hgl" : "input-gamepad")
                                    fallback: "input-gamepad"
                                    implicitWidth: Kirigami.Units.iconSizes.huge
                                    implicitHeight: Kirigami.Units.iconSizes.huge
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignHCenter
                                    wrapMode: Text.Wrap
                                    maximumLineCount: 3
                                    elide: Text.ElideRight
                                    font.bold: true
                                    text: tile.modelData.name
                                }
                            }
                            RowLayout {
                                anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                                          margins: Kirigami.Units.smallSpacing }
                                QQC2.Button {
                                    icon.name: "media-playback-start"
                                    text: L.t("Play")
                                    highlighted: true
                                    onClicked: page.play(tile.modelData)
                                }
                                Item { Layout.fillWidth: true }
                                QQC2.Button {
                                    visible: tile.modelData.settings === true
                                    icon.name: "configure"
                                    text: L.t("Settings")
                                    display: QQC2.AbstractButton.IconOnly
                                    QQC2.ToolTip.visible: hovered
                                    QQC2.ToolTip.text: text
                                    onClicked: { gameDialog.gameId = tile.modelData.id; gameDialog.open(); }
                                }
                            }
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            text: tile.modelData.name
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            opacity: 0.7
                            font: Kirigami.Theme.smallFont
                            // "Steam · 🟢 Runs well"
                            // a game that didn't start says so instead of the reports' verdict
                            text: [tile.sourceText,
                                   tile.modelData.doctor && tile.modelData.doctor.failures > 0 && tile.modelData.doctor.status !== "works"
                                   ? "⚠️ " + L.t("Didn't start")
                                   : tile.modelData.check && tile.modelData.check.badgeText
                                     ? tile.modelData.check.mark + " " + tile.modelData.check.badgeText : ""]
                                  .filter(t => t !== "").join(" · ")
                        }
                    }
                }
            }
        }

        // --- Game mode: set up for the game by itself while one runs (game_mode_ctl.py, /usr/libexec/sloth-os/game-mode)
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                RowLayout {
                    Layout.fillWidth: true
                    Kirigami.Icon {
                        source: "input-gamepad"
                        implicitWidth: Kirigami.Units.iconSizes.medium
                        implicitHeight: Kirigami.Units.iconSizes.medium
                    }
                    Kirigami.Heading { level: 3; Layout.fillWidth: true; text: L.t("Game mode") }
                    QQC2.Switch {
                        checked: gameMode.enabled
                        onToggled: {
                            gameMode.setEnabled(checked);
                            checked = Qt.binding(() => gameMode.enabled);
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: L.t("While a game runs, Sloth OS gets the computer ready for it by itself: notifications wait, the game gets more power (the best performance mode when plugged in), and updates and backups wait until you stop playing. Afterwards everything goes back.")
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: gameMode.enabled && gameMode.playing !== ""
                    type: Kirigami.MessageType.Positive
                    text: L.tf("Game mode is on now: {game}", { game: gameMode.playing })
                }
            }
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
    }

    // A game's settings (FPS, performance mode, upscaling, moving to another drive): the card it always had
    Kirigami.Dialog {
        id: gameDialog
        property string gameId: ""
        readonly property var game: games.games.find(g => g.id === gameId) || null
        title: game ? game.name : ""
        preferredWidth: Kirigami.Units.gridUnit * 34
        padding: Kirigami.Units.largeSpacing
        standardButtons: Kirigami.Dialog.Close
        ColumnLayout {
            // the dialog sizes itself from its content: a width of its own, the height from the card
            implicitWidth: Kirigami.Units.gridUnit * 32
            spacing: Kirigami.Units.largeSpacing
            Repeater {
                model: gameDialog.game ? [gameDialog.game] : []
                delegate: Kirigami.AbstractCard {
                    id: gameCard
                    required property var modelData
                    readonly property bool locked: gameCard.modelData.source === "steam" && games.steamRunning
                    property var moveTargets: []  // filled by "Move to another drive…": the choices shown
                    Layout.fillWidth: true
                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.largeSpacing
                        // --- What's wrong with the game? (games.py, sloth_common.steam_doctor) ----------------
                        Kirigami.AbstractCard {
                            id: doctorCard
                            readonly property var d: gameCard.modelData.doctor || ({})
                            Layout.fillWidth: true
                            visible: d.failures > 0
                            contentItem: ColumnLayout {
                                spacing: Kirigami.Units.smallSpacing
                                RowLayout {
                                    Kirigami.Icon {
                                        source: doctorCard.d.status === "works" ? "emblem-ok-symbolic" : "dialog-warning"
                                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                                    }
                                    Kirigami.Heading { level: 4; text: L.t("What's wrong with the game?") }
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    text: L.tf("Closed right after starting: {count} × so far, the last time after {seconds} seconds.",
                                               { count: doctorCard.d.failures || 0, seconds: doctorCard.d.lastSeconds || 0 })
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    font.bold: true
                                    text: doctorCard.d.native
                                          ? L.t("This is the game's Linux version, so Sloth OS can't change how it starts. In Steam, the game's Properties → Installed Files → Verify integrity of game files often helps.")
                                          : doctorCard.d.status === "works"
                                            ? L.tf("It works with this: {fix}.", { fix: doctorCard.d.stepText })
                                          : doctorCard.d.status === "trying"
                                            ? L.tf("Sloth OS is trying: {fix}. Start the game again to see whether it helps.", { fix: doctorCard.d.stepText })
                                          : doctorCard.d.status === "gave_up" || !doctorCard.d.canTry
                                            ? L.t("Nothing helped so far. The players' reports under Will it run? may tell more, and you can ask for help in Help and feedback.")
                                          : L.t("Sloth OS can try settings that often help, one after the other.")
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    opacity: 0.7
                                    visible: !doctorCard.d.native && doctorCard.d.canTry === true
                                    text: L.t("For this, Steam closes for a moment, and the game starts again by itself.")
                                }
                                RowLayout {
                                    visible: games.fixingId === gameCard.modelData.id
                                    QQC2.BusyIndicator { running: parent.visible }
                                    QQC2.Label { text: L.t("Closing Steam and saving the setting…") }
                                }
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    visible: games.fixingId !== gameCard.modelData.id
                                    QQC2.Button {
                                        visible: !doctorCard.d.native && doctorCard.d.canTry === true && doctorCard.d.status !== "works"
                                        highlighted: true
                                        icon.name: "tools-wizard"
                                        text: doctorCard.d.changed ? L.t("Try the next fix") : L.t("Try a fix")
                                        onClicked: games.tryFix(gameCard.modelData.id)
                                    }
                                    QQC2.Button {
                                        visible: doctorCard.d.changed === true
                                        icon.name: "edit-undo"
                                        text: L.t("Undo the fixes")
                                        onClicked: games.undoFix(gameCard.modelData.id)
                                    }
                                    QQC2.Button {
                                        visible: doctorCard.d.changed !== true
                                        flat: true
                                        text: L.t("It was me who closed it")
                                        onClicked: games.forgetProblem(gameCard.modelData.id)
                                    }
                                }
                            }
                        }
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
                                // the name is the dialog's title already
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
