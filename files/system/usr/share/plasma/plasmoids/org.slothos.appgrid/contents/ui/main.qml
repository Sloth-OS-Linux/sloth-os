/*
    Sloth OS app grid: every app as a full-screen grid of icons, in pages, with a search field on top.
    style "ubuntu": as GNOME's "Show Apps" on Ubuntu: the desktop shrinks to a small live picture at the top (the
                    wallpaper with the open windows, as the taskbar's previews show them) and the grid rises below.
    style "mac":    the grid grows out of the dock button and shrinks back into it, as the Mac's Launchpad.
    style "chromeos": not full-screen: a bubble above the shelf's launcher button, as ChromeOS's launcher (the search,
                    the recently used apps in a row, then every app in a grid that scrolls).
    The window, the app list and the search come from KDE's own launcher (Kicker, the Application Dashboard);
    the search field's text, the tooltip and the menu use KDE's translations.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.private.kicker as Kicker
import org.kde.pipewire as PipeWire
import org.kde.taskmanager as TaskManager

PlasmoidItem {
    id: root

    readonly property bool mac: Plasmoid.configuration.style === "mac"
    readonly property bool chromeos: Plasmoid.configuration.style === "chromeos"
    // the flat, alphabetical list of every app (null until the root model is filled)
    property var allApps: null
    // bumped when the list is rebuilt: the tiles read their row again
    property int revision: 0
    // the desktop's wallpaper on this screen, for the small picture of the desktop (Ubuntu style)
    property string wallpaper: ""
    readonly property string wallpaperHelper: "/usr/libexec/sloth-os/desktop-wallpaper"

    Plasmoid.icon: Plasmoid.configuration.icon
    toolTipMainText: i18nd("libkicker", "All Applications")
    toolTipSubText: ""

    // Ubuntu and Mac: a button in the panel, never a popup (the grid is a window of its own);
    // ChromeOS: Plasma's own popup above the button (the bubble)
    preferredRepresentation: chromeos ? compactRepresentation : fullRepresentation
    switchWidth: 0
    switchHeight: 0
    compactRepresentation: chromeos ? bubbleButton : null
    fullRepresentation: chromeos ? bubble : button

    Component.onCompleted: {
        if (Plasmoid.hasOwnProperty("activationTogglesExpanded")) {
            Plasmoid.activationTogglesExpanded = chromeos;
        }
    }

    function findAllApps() {
        for (let i = 0; i < rootModel.count; ++i) {
            const model = rootModel.modelForRow(i);
            if (model && model.description === "KICKER_ALL_MODEL") {
                return model;
            }
        }
        return null;
    }

    function refreshApps() {
        allApps = findAllApps();
        revision++;
    }

    Kicker.RootModel {
        id: rootModel

        appletInterface: root
        flat: true
        sorted: true
        appNameFormat: 0 // the name only, as on Ubuntu and the Mac
        showAllApps: true
        showAllAppsCategorized: false
        showTopLevelItems: false
        showSeparators: false
        showRootSeparator: false
        showRecentApps: false
        showRecentDocs: false
        showRecentFolders: false
        showPowerSession: false
        showFavoritesPlaceholder: false
        highlightNewlyInstalledApps: false

        onRefreshed: root.refreshApps()
        onCountChanged: root.refreshApps()
        Component.onCompleted: root.refreshApps()
    }

    Kicker.RunnerModel {
        id: runnerModel

        appletInterface: root
        mergeResults: true
        runners: ["krunner_services", "krunner_systemsettings", "calculator", "unitconverter"]
    }

    Kicker.ProcessRunner {
        id: processRunner
    }

    // runs the wallpaper helper; its answer is the image's path (or nothing)
    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            root.wallpaper = (data["stdout"] || "").trim();
            disconnectSource(source);
        }
    }

    function readWallpaper(width, height) {
        const screen = Plasmoid.containment ? Math.max(0, Plasmoid.containment.screen) : 0;
        executable.connectSource(`${wallpaperHelper} ${screen} ${Math.round(width)}x${Math.round(height)}`);
    }

    TaskManager.VirtualDesktopInfo {
        id: desktopInfo
    }

    TaskManager.ActivityInfo {
        id: activityInfo
    }

    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: i18ndc("plasma_applet_org.kde.plasma.kicker", "@action:inmenu launches kmenuedit", "Edit Applications…")
            icon.name: "kmenuedit"
            visible: Plasmoid.immutability !== PlasmaCore.Types.SystemImmutable
            onTriggered: processRunner.runMenuEditor()
        }
    ]

    // one app: its icon with the name below, a soft highlight under the mouse or the keyboard
    component Tile: Item {
        id: tile

        required property string label
        required property var iconSource
        required property int iconSize
        property bool current: false
        // white over the dimmed desktop; the bubble passes the theme's text color
        property color textColor: "white"
        signal launched()

        Accessible.role: Accessible.Button
        Accessible.name: label

        Rectangle {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            radius: Kirigami.Units.cornerRadius * 3
            color: tile.textColor
            opacity: tileMouse.pressed ? 0.22 : (tileMouse.containsMouse || tile.current ? 0.12 : 0)
            Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
        }

        Kirigami.Icon {
            id: tileIcon
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: Kirigami.Units.largeSpacing
            width: tile.iconSize
            height: tile.iconSize
            source: tile.iconSource
            animated: false
        }

        PlasmaComponents.Label {
            anchors.top: tileIcon.bottom
            anchors.topMargin: Kirigami.Units.smallSpacing
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: Kirigami.Units.smallSpacing
            anchors.rightMargin: Kirigami.Units.smallSpacing
            horizontalAlignment: Text.AlignHCenter
            text: tile.label
            textFormat: Text.PlainText
            color: tile.textColor
            elide: Text.ElideRight
            wrapMode: Text.Wrap
            maximumLineCount: 2
        }

        MouseArea {
            id: tileMouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: tile.launched()
        }
    }

    // ChromeOS: the recently used apps, the first row of the bubble
    Kicker.RecentUsageModel {
        id: recentApps
        shownItems: Kicker.RecentUsageModel.OnlyApps
        ordering: 0 // the most recent first
    }

    Component {
        id: bubbleButton

        Kirigami.Icon {
            source: Plasmoid.icon
            active: bubbleButtonMouse.containsMouse
            roundToIconSize: true
            Layout.maximumWidth: Kirigami.Units.iconSizes.huge
            Layout.maximumHeight: Kirigami.Units.iconSizes.huge

            MouseArea {
                id: bubbleButtonMouse
                anchors.fill: parent
                hoverEnabled: true
                property bool wasExpanded: false
                onPressed: wasExpanded = root.expanded
                onClicked: root.expanded = !wasExpanded
            }
        }
    }

    // ChromeOS: the launcher bubble (in Plasma's popup above the shelf)
    Component {
        id: bubble

        Item {
            id: bubbleItem

            readonly property int iconSize: Kirigami.Units.iconSizes.large
            readonly property int columns: 5
            readonly property int cellWidth: iconSize + Kirigami.Units.gridUnit * 3
            readonly property int cellHeight: iconSize + Kirigami.Units.gridUnit * 3.5
            readonly property bool searching: bubbleSearch.text !== ""

            function launch(model, row) {
                model.trigger(row, "", null);
                root.expanded = false;
            }

            Layout.preferredWidth: columns * cellWidth + Kirigami.Units.gridUnit * 2
            Layout.minimumWidth: Layout.preferredWidth
            Layout.preferredHeight: Kirigami.Units.gridUnit * 32
            Layout.minimumHeight: Kirigami.Units.gridUnit * 24

            Connections {
                target: root
                function onExpandedChanged() {
                    if (root.expanded) {
                        bubbleSearch.clear();
                        bubbleSearch.forceActiveFocus(Qt.OtherFocusReason);
                        allGrid.positionViewAtBeginning();
                    } else {
                        runnerModel.query = "";
                    }
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.largeSpacing

                PlasmaExtras.SearchField {
                    id: bubbleSearch
                    Layout.fillWidth: true
                    focus: true
                    onTextChanged: runnerModel.query = text
                    // Enter starts the first result
                    function launchFirst() {
                        if (bubbleItem.searching && resultsGrid.count > 0) {
                            bubbleItem.launch(resultsGrid.model, 0);
                        }
                    }
                    Keys.onReturnPressed: launchFirst()
                    Keys.onEnterPressed: launchFirst()
                    Keys.onEscapePressed: {
                        if (bubbleItem.searching) {
                            clear();
                        } else {
                            root.expanded = false;
                        }
                    }
                }

                // the recently used apps: one row
                GridView {
                    id: recentGrid
                    Layout.fillWidth: true
                    Layout.preferredHeight: bubbleItem.cellHeight
                    visible: !bubbleItem.searching && count > 0
                    interactive: false
                    clip: true
                    cellWidth: bubbleItem.cellWidth
                    cellHeight: bubbleItem.cellHeight
                    model: recentApps
                    delegate: Tile {
                        required property int index
                        required property string display
                        required property var decoration
                        width: bubbleItem.cellWidth
                        height: bubbleItem.cellHeight
                        iconSize: bubbleItem.iconSize
                        textColor: Kirigami.Theme.textColor
                        label: display
                        iconSource: decoration
                        onLaunched: bubbleItem.launch(recentApps, index)
                    }
                }

                Kirigami.Separator {
                    Layout.fillWidth: true
                    visible: recentGrid.visible
                }

                // every app, alphabetical, scrolling
                GridView {
                    id: allGrid
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: !bubbleItem.searching
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    cellWidth: bubbleItem.cellWidth
                    cellHeight: bubbleItem.cellHeight
                    model: root.allApps
                    QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                    delegate: Tile {
                        required property int index
                        required property string display
                        required property var decoration
                        width: bubbleItem.cellWidth
                        height: bubbleItem.cellHeight
                        iconSize: bubbleItem.iconSize
                        textColor: Kirigami.Theme.textColor
                        label: display
                        iconSource: decoration
                        onLaunched: bubbleItem.launch(root.allApps, index)
                    }
                }

                // the search results
                GridView {
                    id: resultsGrid
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: bubbleItem.searching
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    cellWidth: bubbleItem.cellWidth
                    cellHeight: bubbleItem.cellHeight
                    model: bubbleItem.searching && runnerModel.count > 0 ? runnerModel.modelForRow(0) : null
                    QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                    delegate: Tile {
                        required property int index
                        required property string display
                        required property var decoration
                        width: bubbleItem.cellWidth
                        height: bubbleItem.cellHeight
                        iconSize: bubbleItem.iconSize
                        textColor: Kirigami.Theme.textColor
                        current: index === 0
                        label: display
                        iconSource: decoration
                        onLaunched: bubbleItem.launch(resultsGrid.model, index)
                    }
                }
            }
        }
    }

    Component {
        id: button

        Item {
            id: buttonItem

            Layout.maximumWidth: Kirigami.Units.iconSizes.huge
            Layout.maximumHeight: Kirigami.Units.iconSizes.huge

            // the wallpaper is read ahead, so the first opening already has it
            Component.onCompleted: {
                if (!root.mac) {
                    root.readWallpaper(Screen.width, Screen.height);
                }
            }

            Kirigami.Icon {
                anchors.fill: parent
                source: Plasmoid.icon
                active: buttonMouse.containsMouse
                roundToIconSize: true
            }

            MouseArea {
                id: buttonMouse
                anchors.fill: parent
                hoverEnabled: !gridWindow.visible
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: root.toolTipMainText
                Keys.onReturnPressed: gridWindow.open()
                Keys.onEnterPressed: gridWindow.open()
                Keys.onSpacePressed: gridWindow.open()
                onClicked: gridWindow.open()
            }

            Connections {
                target: Plasmoid
                // the Meta key and the widget's shortcut
                function onActivated() {
                    if (gridWindow.visible) {
                        gridWindow.dismiss();
                    } else {
                        gridWindow.open();
                    }
                }
            }

            // the opening and closing animation (the window takes only its main item as a child)
            NumberAnimation {
                id: progressAnimation
                target: gridWindow
                property: "progress"
                duration: root.mac ? Kirigami.Units.longDuration * 1.5 : Kirigami.Units.longDuration
                easing.type: Easing.OutCubic
                onFinished: {
                    if (gridWindow.closing) {
                        gridWindow.closing = false;
                        gridWindow.close();
                    }
                }
            }

            Kicker.DashboardWindow {
                id: gridWindow

                // 0 = closed, 1 = open; the opening and closing animations run on this
                property real progress: 0
                property bool closing: false
                // where the grid grows from (the Mac style): the button's centre in the window
                property point origin: Qt.point(width / 2, height)
                readonly property bool searching: searchField.text !== ""

                visualParent: buttonItem
                backgroundColor: "transparent"
                keyEventProxy: searchField

                function open() {
                    if (visible) {
                        return;
                    }
                    closing = false;
                    progress = 0;
                    toggle();
                }

                // close with the animation (Esc, a click beside the icons, another window)
                function dismiss() {
                    if (!visible || closing) {
                        return;
                    }
                    closing = true;
                    progressAnimation.to = 0;
                    progressAnimation.restart();
                }

                // an app was started: go at once, the app's own window takes over
                function launched() {
                    closing = false;
                    progressAnimation.stop();
                    close();
                }

                function updateOrigin() {
                    const p = buttonItem.mapToGlobal(buttonItem.width / 2, buttonItem.height / 2);
                    const x = p.x - gridWindow.x;
                    const y = p.y - gridWindow.y;
                    const inside = x >= 0 && y >= 0 && x <= width && y <= height;
                    origin = inside ? Qt.point(x, y) : Qt.point(width / 2, height);
                }

                onVisibleChanged: {
                    if (visible) {
                        if (!root.mac) {
                            root.readWallpaper(width, height);
                        }
                        searchField.clear();
                        searchField.forceActiveFocus(Qt.OtherFocusReason);
                        pages.positionViewAtBeginning();
                        pages.currentIndex = 0;
                        updateOrigin();
                        progressAnimation.to = 1;
                        progressAnimation.restart();
                    } else {
                        progress = 0;
                        closing = false;
                        runnerModel.query = "";
                    }
                }

                onActiveChanged: {
                    if (!active && visible) {
                        dismiss();
                    }
                }

                onKeyEscapePressed: {
                    if (searching) {
                        searchField.clear();
                    } else {
                        dismiss();
                    }
                }

                mainItem: Item {
                    id: content

                    anchors.fill: parent

                    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
                    Kirigami.Theme.inherit: false

                    readonly property int iconSize: Math.round(Kirigami.Units.iconSizes.huge * (root.mac ? 1.25 : 1.5))
                    readonly property int cellWidth: iconSize + Kirigami.Units.gridUnit * 4
                    readonly property int cellHeight: iconSize + Kirigami.Units.gridUnit * 4
                    readonly property int columns: Math.max(1, Math.min(root.mac ? 7 : 8, Math.floor(pages.width / cellWidth)))
                    readonly property int rows: Math.max(1, Math.min(root.mac ? 5 : 4, Math.floor(pages.height / cellHeight)))
                    readonly property int pageSize: columns * rows
                    readonly property int appCount: root.allApps ? root.allApps.count : 0

                    // the desktop behind dims (the window blurs it too)
                    Rectangle {
                        anchors.fill: parent
                        color: "black"
                        opacity: gridWindow.progress * (root.mac ? 0.45 : 0.6)
                    }

                    // a click beside the icons closes the grid
                    MouseArea {
                        anchors.fill: parent
                        onClicked: gridWindow.dismiss()
                    }

                    // Ubuntu style: the desktop, shrunk from the whole screen into the slot above the grid, with
                    // its open windows live (the windows of this screen, workspace and activity, not minimized)
                    Item {
                        id: desktopPicture

                        readonly property real p: gridWindow.progress
                        // the screen's size and where it is: the windows' places are given in these
                        readonly property rect screenRect: Qt.rect(gridWindow.x, gridWindow.y, content.width, content.height)
                        readonly property real scale: width / Math.max(1, content.width)

                        visible: !root.mac && content.width > 0
                        // fades in at the start: the real desktop is right behind it
                        opacity: gridWindow.searching ? 0 : Math.min(1, p * 4)

                        x: desktopSlot.x * p
                        y: desktopSlot.y * p
                        width: content.width + (desktopSlot.width - content.width) * p
                        height: content.height + (desktopSlot.height - content.height) * p

                        Kirigami.ShadowedRectangle {
                            anchors.fill: parent
                            radius: Kirigami.Units.cornerRadius * 4 * desktopPicture.p
                            color: "#202326"
                            shadow.size: Kirigami.Units.gridUnit * desktopPicture.p
                            shadow.color: Qt.rgba(0, 0, 0, 0.5)
                        }

                        Image {
                            id: wallpaperImage
                            anchors.fill: parent
                            source: root.wallpaper ? "file://" + root.wallpaper : ""
                            fillMode: Image.PreserveAspectCrop
                            sourceSize.width: content.width / 2
                            asynchronous: true
                            visible: false
                        }

                        Kirigami.ShadowedTexture {
                            anchors.fill: parent
                            source: wallpaperImage.status === Image.Ready ? wallpaperImage : null
                            radius: Kirigami.Units.cornerRadius * 4 * desktopPicture.p
                            color: "transparent"
                        }

                        // a click on the desktop goes back to it
                        MouseArea {
                            anchors.fill: parent
                            onClicked: gridWindow.dismiss()
                        }

                        Item {
                            anchors.fill: parent
                            clip: true

                            Repeater {
                                model: TaskManager.TasksModel {
                                    id: windowsModel

                                    groupMode: TaskManager.TasksModel.GroupDisabled
                                    filterByScreen: true
                                    screenGeometry: desktopPicture.screenRect
                                    filterByVirtualDesktop: true
                                    virtualDesktop: desktopInfo.currentDesktop
                                    filterByActivity: true
                                    activity: activityInfo.currentActivity
                                    filterMinimized: true
                                    filterHidden: true
                                }

                                delegate: Item {
                                    id: windowPicture

                                    required property int index
                                    // the task model's roles start with a capital letter (Geometry, WinIdList…),
                                    // which a QML property name cannot: they are read from the model
                                    required property var model
                                    readonly property rect geometry: model.Geometry
                                    readonly property var winIds: model.WinIdList || []

                                    x: (geometry.x - desktopPicture.screenRect.x) * desktopPicture.scale
                                    y: (geometry.y - desktopPicture.screenRect.y) * desktopPicture.scale
                                    width: geometry.width * desktopPicture.scale
                                    height: geometry.height * desktopPicture.scale
                                    z: model.StackingOrder

                                    // the window's live picture; while it starts (or if it cannot), its icon
                                    Loader {
                                        id: liveLoader
                                        anchors.fill: parent
                                        active: gridWindow.visible && !root.mac && windowPicture.winIds.length > 0
                                            && typeof windowPicture.winIds[0] === "string"
                                        sourceComponent: PipeWire.PipeWireSourceItem {
                                            nodeId: screencast.nodeId
                                            TaskManager.ScreencastingRequest {
                                                id: screencast
                                                uuid: windowPicture.winIds[0]
                                            }
                                        }
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        visible: !(liveLoader.item && liveLoader.item.ready)
                                        color: Qt.rgba(1, 1, 1, 0.12)
                                        radius: Kirigami.Units.cornerRadius
                                        Kirigami.Icon {
                                            anchors.centerIn: parent
                                            width: Math.min(parent.width, parent.height) / 2
                                            height: width
                                            source: windowPicture.model.decoration
                                        }
                                    }

                                    // a click on a window goes back to it
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: {
                                            windowsModel.requestActivate(windowsModel.makeModelIndex(windowPicture.index));
                                            gridWindow.launched();
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item {
                        id: layer

                        anchors.fill: parent
                        opacity: gridWindow.progress

                        transform: [
                            Scale {
                                origin.x: root.mac ? gridWindow.origin.x : layer.width / 2
                                origin.y: root.mac ? gridWindow.origin.y : layer.height / 2
                                xScale: root.mac ? 0.1 + 0.9 * gridWindow.progress : 0.96 + 0.04 * gridWindow.progress
                                yScale: xScale
                            },
                            Translate {
                                y: root.mac ? 0 : (1 - gridWindow.progress) * Kirigami.Units.gridUnit * 6
                            }
                        ]

                        PlasmaExtras.SearchField {
                            id: searchField

                            anchors.horizontalCenter: parent.horizontalCenter
                            y: Kirigami.Units.gridUnit * 3
                            width: Kirigami.Units.gridUnit * 20
                            focus: true

                            onTextChanged: runnerModel.query = text

                            Keys.onLeftPressed: event => {
                                if (gridWindow.searching) {
                                    event.accepted = false;
                                } else {
                                    pages.decrementCurrentIndex();
                                }
                            }
                            Keys.onRightPressed: event => {
                                if (gridWindow.searching) {
                                    event.accepted = false;
                                } else {
                                    pages.incrementCurrentIndex();
                                }
                            }
                            Keys.onPressed: event => {
                                if (event.key === Qt.Key_PageUp && !gridWindow.searching) {
                                    pages.decrementCurrentIndex();
                                    event.accepted = true;
                                } else if (event.key === Qt.Key_PageDown && !gridWindow.searching) {
                                    pages.incrementCurrentIndex();
                                    event.accepted = true;
                                }
                            }
                            // Enter starts the first result
                            Keys.onReturnPressed: results.launchFirst()
                            Keys.onEnterPressed: results.launchFirst()
                        }

                        // Ubuntu style: where the small picture of the desktop sits, under the search field
                        Item {
                            id: desktopSlot

                            readonly property real aspect: content.width / Math.max(1, content.height)

                            anchors.top: searchField.bottom
                            anchors.topMargin: Kirigami.Units.gridUnit * 1.5
                            anchors.horizontalCenter: parent.horizontalCenter
                            height: root.mac ? 0 : Math.min(content.height * 0.26, content.width * 0.5 / aspect)
                            width: height * aspect
                        }

                        // the apps, a page at a time (swipe, the mouse wheel, the arrow keys or the dots)
                        ListView {
                            id: pages

                            anchors {
                                top: root.mac ? searchField.bottom : desktopSlot.bottom
                                topMargin: Kirigami.Units.gridUnit * (root.mac ? 2 : 1)
                                bottom: dots.top
                                bottomMargin: Kirigami.Units.gridUnit
                                horizontalCenter: parent.horizontalCenter
                            }
                            width: Math.min(parent.width - Kirigami.Units.gridUnit * 8, content.cellWidth * (root.mac ? 7 : 8))

                            visible: !gridWindow.searching
                            orientation: ListView.Horizontal
                            snapMode: ListView.SnapOneItem
                            highlightRangeMode: ListView.StrictlyEnforceRange
                            highlightMoveDuration: Kirigami.Units.longDuration
                            boundsBehavior: Flickable.StopAtBounds
                            clip: true
                            cacheBuffer: width
                            model: Math.max(1, Math.ceil(content.appCount / content.pageSize))

                            delegate: Item {
                                id: page

                                required property int index

                                width: pages.width
                                height: pages.height

                                // the empty space between and below the icons closes the grid too
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: gridWindow.dismiss()
                                }

                                Grid {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.verticalCenter: parent.verticalCenter
                                    columns: content.columns
                                    // a full page's size, so the last, shorter page lines up with the others
                                    width: content.columns * content.cellWidth
                                    height: content.rows * content.cellHeight

                                    Repeater {
                                        model: Math.max(0, Math.min(content.pageSize,
                                                                    content.appCount - page.index * content.pageSize))

                                        delegate: Tile {
                                            required property int index
                                            readonly property int row: page.index * content.pageSize + index
                                            readonly property var modelIndex: {
                                                root.revision;
                                                return root.allApps ? root.allApps.index(row, 0) : null;
                                            }

                                            width: content.cellWidth
                                            height: content.cellHeight
                                            iconSize: content.iconSize
                                            label: modelIndex ? (root.allApps.data(modelIndex, Qt.DisplayRole) ?? "") : ""
                                            iconSource: modelIndex ? root.allApps.data(modelIndex, Qt.DecorationRole) : ""
                                            onLaunched: {
                                                root.allApps.trigger(row, "", null);
                                                gridWindow.launched();
                                            }
                                        }
                                    }
                                }
                            }

                            // the mouse wheel turns the pages, one notch a page
                            WheelHandler {
                                property real collected: 0
                                target: null
                                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                onWheel: event => {
                                    const delta = Math.abs(event.angleDelta.y) > Math.abs(event.angleDelta.x)
                                        ? event.angleDelta.y : event.angleDelta.x;
                                    collected += delta;
                                    if (collected <= -120) {
                                        pages.incrementCurrentIndex();
                                        collected = 0;
                                    } else if (collected >= 120) {
                                        pages.decrementCurrentIndex();
                                        collected = 0;
                                    }
                                }
                            }
                        }

                        // a dot for each page, the current one bright
                        Row {
                            id: dots

                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: Kirigami.Units.gridUnit * (root.mac ? 6 : 3)
                            spacing: Kirigami.Units.largeSpacing
                            visible: !gridWindow.searching && pages.count > 1

                            Repeater {
                                model: pages.count

                                delegate: Rectangle {
                                    required property int index

                                    width: Kirigami.Units.gridUnit * 0.6
                                    height: width
                                    radius: width / 2
                                    color: "white"
                                    opacity: index === pages.currentIndex ? 0.9 : 0.35

                                    MouseArea {
                                        anchors.fill: parent
                                        anchors.margins: -Kirigami.Units.smallSpacing
                                        onClicked: pages.currentIndex = parent.index
                                    }
                                }
                            }
                        }

                        // the search results: apps first, then settings and the calculator
                        GridView {
                            id: results

                            function launchFirst() {
                                if (count > 0 && model) {
                                    model.trigger(0, "", null);
                                    gridWindow.launched();
                                }
                            }

                            anchors {
                                top: searchField.bottom
                                topMargin: Kirigami.Units.gridUnit * 2
                                bottom: parent.bottom
                                bottomMargin: Kirigami.Units.gridUnit * 3
                                horizontalCenter: parent.horizontalCenter
                            }
                            width: content.cellWidth * Math.min(content.columns, Math.max(1, count))

                            visible: gridWindow.searching
                            cellWidth: content.cellWidth
                            cellHeight: content.cellHeight
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            model: gridWindow.searching && runnerModel.count > 0 ? runnerModel.modelForRow(0) : null

                            delegate: Tile {
                                required property int index
                                required property string display
                                required property var decoration

                                width: content.cellWidth
                                height: content.cellHeight
                                iconSize: content.iconSize
                                label: display
                                iconSource: decoration
                                current: index === 0
                                onLaunched: {
                                    results.model.trigger(index, "", null);
                                    gridWindow.launched();
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
