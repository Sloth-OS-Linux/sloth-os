// Sloth Center – main window: the modules on the left, the selected page on the right.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: L.t("Sloth Center")
    visible: true
    width: Kirigami.Units.gridUnit * 56
    height: Kirigami.Units.gridUnit * 38
    minimumWidth: Kirigami.Units.gridUnit * 30
    minimumHeight: Kirigami.Units.gridUnit * 24

    // The list of modules. Modules with "ready: false" are still being made (ROADMAP phase 3).
    readonly property var modules: [
        { id: "status", name: L.t("System status"), icon: "dialog-information", page: "SystemStatusPage.qml", ready: true },
        { id: "updates", name: L.t("Updates"), icon: "system-software-update", page: "UpdatesPage.qml", ready: true },
        { id: "winprograms", name: L.t("Programs"), icon: "application-x-ms-dos-executable", page: "WinProgramsPage.qml", ready: true },
        { id: "games", name: L.t("Games"), icon: "input-gamepad", page: "GamesPage.qml", ready: true },
        { id: "drivers", name: L.t("Drivers and hardware"), icon: "preferences-devices-cpu", page: "DriversPage.qml", ready: true },
        { id: "services", name: L.t("Services"), icon: "preferences-system-services", page: "ServicesPage.qml", ready: true },
        { id: "accounts", name: L.t("Account and security"), icon: "preferences-system-users", page: "AccountsPage.qml", ready: true },
        { id: "appearance", name: L.t("Appearance"), icon: "preferences-desktop-theme-global", page: "AppearancePage.qml", ready: true },
        { id: "parental", name: L.t("Parental controls"), icon: "user-group-properties", ready: false,
          description: L.t("Child accounts, age-appropriate apps and screen time. This part is coming in a future update.") },
        { id: "health", name: L.t("System health"), icon: "dialog-information", page: "HealthPage.qml", ready: true },
        { id: "help", name: L.t("Help"), icon: "help-contents", page: "HelpPage.qml", ready: true },
        { id: "feedback", name: L.t("Feedback"), icon: "mail-message-new", page: "FeedbackPage.qml", ready: true },
        { id: "usbguide", name: L.t("Create installation media"), icon: "drive-removable-media-usb", page: "UsbGuidePage.qml", ready: true },
        { id: "backup", name: L.t("File backup"), icon: "backup", page: "BackupPage.qml", ready: true },
        { id: "disks", name: L.t("Disks"), icon: "drive-harddisk", page: "DisksPage.qml", ready: true },
        { id: "containers", name: L.t("Developer environments"), icon: "utilities-terminal", page: "ContainersPage.qml", ready: true },
        { id: "reset", name: L.t("Reset this PC"), icon: "edit-undo", page: "ResetPage.qml", ready: true },
        { id: "advanced", name: L.t("Advanced settings"), icon: "configure", page: "AdvancedPage.qml", ready: true },
        { id: "devpanel", name: L.t("Developer panel"), icon: "applications-development", page: "DevPanelPage.qml",
          ready: true }
    ]
    property int currentIndex: 0
    property int guideStep: 0

    // The first-run guide: each step lights up its pages in the list on the left, the rest of the window goes dark
    readonly property var guideSteps: [
        { modules: ["updates"], title: L.t("Keep Sloth OS up to date"),
          text: L.t("The Updates page installs system updates and lets you return to the previous version if an update causes trouble.") },
        { modules: ["winprograms", "games"], title: L.t("Find and manage programs"),
          text: L.t("Programs is where you install and start Windows programs. Games has settings for Steam and other game tools.") },
        { modules: ["appearance"], title: L.t("Change how it looks"),
          text: L.t("Appearance switches the taskbar layout and the colors, the same ones as in the welcome wizard. You can change them any time.") },
        { modules: ["feedback", "backup", "disks"], title: L.t("Back up files and get help"),
          text: L.t("File backup shows saved copies of your files. Feedback is the place to ask for help, and Disks can help bring files over from Windows.") }
    ]

    function openGuide() {
        guideStep = 0;
        guideDialog.open();
        Qt.callLater(guideDialog.place);
    }

    function openModule(index) {
        currentIndex = index;
        const m = modules[index];
        pageStack.clear();
        if (m.ready) {
            if (["status", "health", "disks", "help"].includes(m.id))
                pageStack.push(Qt.resolvedUrl(m.page), { navigation: root });
            else
                pageStack.push(Qt.resolvedUrl(m.page));
        } else {
            pageStack.push(comingSoon, { module: m });
        }
    }

    // From another page (Help): opens a module by its id
    function openModuleById(id) {
        const index = modules.findIndex(m => m.id === id);
        if (index >= 0)
            openModule(index);
    }

    globalDrawer: Kirigami.OverlayDrawer {
        edge: Qt.LeftEdge
        modal: false
        handleVisible: false
        width: Kirigami.Units.gridUnit * 14
        leftPadding: 0
        rightPadding: 0
        topPadding: 0
        bottomPadding: 0

        contentItem: ColumnLayout {
            spacing: 0

            RowLayout {
                Layout.margins: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: "sloth-os"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                Kirigami.Heading {
                    text: L.t("Sloth Center")
                    level: 2
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            QQC2.ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ListView {
                    id: moduleList
                    model: root.modules
                    delegate: QQC2.ItemDelegate {
                        required property var modelData
                        required property int index
                        width: ListView.view.width
                        highlighted: index === root.currentIndex
                        icon.name: modelData.icon
                        text: modelData.name
                        onClicked: root.openModule(index)
                    }
                }
            }

            QQC2.Button {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.smallSpacing
                text: L.t("Open guide")
                icon.name: "help-about"
                onClicked: root.openGuide()
            }
        }
    }

    QQC2.Popup {
        id: guideDialog
        parent: QQC2.Overlay.overlay
        x: 0
        y: 0
        width: root.width
        height: root.height
        padding: 0
        modal: true
        dim: false
        closePolicy: QQC2.Popup.CloseOnEscape
        background: null
        onClosed: guide.markSeen()

        readonly property var step: root.guideSteps[root.guideStep]
        readonly property bool last: root.guideStep === root.guideSteps.length - 1
        // The lit-up area: the step's pages in the list, together
        property real spotX: 0
        property real spotY: 0
        property real spotW: 0
        property real spotH: 0
        Behavior on spotY { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.InOutCubic } }
        Behavior on spotH { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.InOutCubic } }

        function place() {
            const rows = guideDialog.step.modules.map(id => root.modules.findIndex(m => m.id === id)).filter(i => i >= 0);
            if (!rows.length)
                return;
            // scroll the list so that every page of the step can be seen
            moduleList.positionViewAtIndex(Math.max(...rows), ListView.Contain);
            moduleList.positionViewAtIndex(Math.min(...rows), ListView.Contain);
            let top = Infinity, bottom = -Infinity, left = Infinity, right = -Infinity;
            for (const i of rows) {
                const item = moduleList.itemAtIndex(i);
                if (!item)
                    continue;
                const p = item.mapToItem(spot, 0, 0);
                top = Math.min(top, p.y);
                bottom = Math.max(bottom, p.y + item.height);
                left = Math.min(left, p.x);
                right = Math.max(right, p.x + item.width);
            }
            if (top === Infinity) {
                // the list is not laid out yet (the window is just opening): a moment later
                placeAgain.restart();
                return;
            }
            guideDialog.spotX = left;
            guideDialog.spotY = top;
            guideDialog.spotW = right - left;
            guideDialog.spotH = bottom - top;
        }

        Timer {
            id: placeAgain
            interval: 150
            onTriggered: if (guideDialog.visible) guideDialog.place()
        }

        Connections {
            target: root
            function onGuideStepChanged() { if (guideDialog.visible) Qt.callLater(guideDialog.place) }
            function onWidthChanged() { if (guideDialog.visible) Qt.callLater(guideDialog.place) }
            function onHeightChanged() { if (guideDialog.visible) Qt.callLater(guideDialog.place) }
        }

        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Kirigami.Units.longDuration } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Kirigami.Units.shortDuration } }

        contentItem: Item {
            id: spot
            readonly property color shade: Qt.rgba(0, 0, 0, 0.62)

            // Everything outside the lit-up area is dark (four pieces around it); clicks do not go through
            MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: wheel => wheel.accepted = true }
            Rectangle { color: spot.shade; x: 0; y: 0; width: parent.width; height: guideDialog.spotY }
            Rectangle {
                color: spot.shade; x: 0; y: guideDialog.spotY + guideDialog.spotH
                width: parent.width; height: Math.max(0, parent.height - y)
            }
            Rectangle { color: spot.shade; x: 0; y: guideDialog.spotY; width: guideDialog.spotX; height: guideDialog.spotH }
            Rectangle {
                color: spot.shade; x: guideDialog.spotX + guideDialog.spotW; y: guideDialog.spotY
                width: Math.max(0, parent.width - x); height: guideDialog.spotH
            }

            // A gently pulsing frame around the pages
            Rectangle {
                x: guideDialog.spotX - 2
                y: guideDialog.spotY - 2
                width: guideDialog.spotW + 4
                height: guideDialog.spotH + 4
                radius: Kirigami.Units.cornerRadius
                color: "transparent"
                border.width: 2
                border.color: Kirigami.Theme.highlightColor
                SequentialAnimation on opacity {
                    running: guideDialog.visible
                    loops: Animation.Infinite
                    NumberAnimation { from: 1; to: 0.35; duration: 900; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 0.35; to: 1; duration: 900; easing.type: Easing.InOutSine }
                }
            }

            // The explanation next to the pages, with a small pointer towards them
            Rectangle {
                id: bubble
                readonly property real margin: Kirigami.Units.gridUnit
                x: Math.min(guideDialog.spotX + guideDialog.spotW + margin, parent.width - width - Kirigami.Units.smallSpacing)
                y: Math.max(Kirigami.Units.smallSpacing,
                            Math.min(guideDialog.spotY + guideDialog.spotH / 2 - height / 2,
                                     parent.height - height - Kirigami.Units.smallSpacing))
                width: Math.min(Kirigami.Units.gridUnit * 24,
                                parent.width - guideDialog.spotX - guideDialog.spotW - margin - Kirigami.Units.smallSpacing)
                height: bubbleContent.implicitHeight + Kirigami.Units.largeSpacing * 2
                radius: Kirigami.Units.cornerRadius * 2
                color: Kirigami.Theme.backgroundColor
                border.width: 1
                border.color: Kirigami.Theme.highlightColor
                Behavior on y { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.InOutCubic } }

                Rectangle {
                    width: Kirigami.Units.gridUnit * 0.8
                    height: width
                    rotation: 45
                    x: -width / 2
                    y: Math.max(bubble.radius, Math.min(guideDialog.spotY + guideDialog.spotH / 2 - bubble.y - height / 2,
                                                        bubble.height - height - bubble.radius))
                    color: bubble.color
                    border.width: 1
                    border.color: bubble.border.color
                    z: -1
                }

                ColumnLayout {
                    id: bubbleContent
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Kirigami.Units.largeSpacing }
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Label {
                        opacity: 0.7
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: L.t("A quick tour of Sloth Center") + " · " + (root.guideStep + 1) + "/" + root.guideSteps.length
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        level: 2
                        wrapMode: Text.Wrap
                        text: guideDialog.step.title
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: guideDialog.step.text
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        QQC2.Button {
                            text: L.t("Skip guide")
                            flat: true
                            onClicked: guideDialog.close()
                        }
                        Item { Layout.fillWidth: true }
                        QQC2.Button {
                            visible: root.guideStep > 0
                            text: L.t("Back")
                            onClicked: root.guideStep--
                        }
                        QQC2.Button {
                            text: guideDialog.last ? L.t("Done") : L.t("Next")
                            highlighted: true
                            focus: true
                            onClicked: {
                                if (guideDialog.last)
                                    guideDialog.close();
                                else
                                    root.guideStep++;
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: comingSoon
        Kirigami.Page {
            property var module
            title: module ? module.name : ""
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                icon.name: parent.module ? parent.module.icon : ""
                text: L.t("Coming soon")
                explanation: parent.module ? parent.module.description : ""
            }
        }
    }

    // The page to open: sloth-center --page <ID> (e.g. from the NVIDIA notification: drivers)
    Component.onCompleted: {
        openModule(Math.max(0, modules.findIndex(m => m.id === startPage && m.ready)));
        if (!guide.seen)
            openGuide();
    }
}
