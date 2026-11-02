// A small drawing of a taskbar layout (sloth_common.appearance): Sloth Welcome and Sloth Center show the same one
import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    id: screen
    property string kind: ""
    property bool current: false
    readonly property bool topBar: kind === "mac" || kind === "ubuntu"
    // a bar along the whole bottom edge (the others float: the Mac's dock, the floating bar)
    readonly property bool fullBar: ["windows10", "windows11", "windows7", "chromeos"].indexOf(kind) >= 0
    readonly property bool floatingBar: kind === "mac" || kind === "floating"
    readonly property color bar: Qt.alpha(Kirigami.Theme.textColor, 0.35)
    readonly property color dot: Kirigami.Theme.highlightColor
    readonly property color icon: Qt.alpha(Kirigami.Theme.backgroundColor, 0.9)

    radius: Kirigami.Units.cornerRadius
    color: Qt.alpha(Kirigami.Theme.textColor, 0.08)
    border.width: current ? 3 : 1
    border.color: current ? Kirigami.Theme.highlightColor : Qt.rgba(0.5, 0.5, 0.5, 0.4)

    // top bar (macOS, Ubuntu)
    Rectangle {
        id: topBar
        visible: screen.topBar
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 3 }
        height: 6; radius: 2; color: screen.bar
    }
    // bottom taskbar, or a dock / bar floating above the bottom edge
    Rectangle {
        visible: screen.fullBar || screen.floatingBar
        anchors.bottom: parent.bottom
        anchors.bottomMargin: screen.floatingBar ? 8 : 3
        x: screen.floatingBar ? (parent.width - width) / 2 : 3
        width: screen.floatingBar ? Math.max(parent.width * 0.4, icons.width + 10) : parent.width - 6
        height: 12; radius: screen.floatingBar ? 5 : 2
        color: screen.bar
        Row {
            id: icons
            anchors.verticalCenter: parent.verticalCenter
            x: screen.kind === "windows10" || screen.kind === "windows7" ? 4 : (parent.width - width) / 2
            spacing: 3
            Repeater {
                // Windows 7: the Start orb, then task buttons with names (wider)
                model: 4
                Rectangle {
                    required property int index
                    readonly property bool start: index === 0 && ["windows10", "windows11", "windows7", "floating"].indexOf(screen.kind) >= 0
                    width: screen.kind === "windows7" && index > 0 ? 14 : 7
                    height: 7
                    radius: screen.kind === "windows7" && index === 0 ? 3.5 : 2
                    color: start ? screen.dot : screen.icon
                }
            }
        }
        // ChromeOS: the round launcher in the corner, the status bubble on the right
        Rectangle {
            visible: screen.kind === "chromeos"
            anchors.verticalCenter: parent.verticalCenter
            x: 4
            width: 7; height: 7; radius: 3.5
            color: screen.dot
        }
        Rectangle {
            visible: screen.kind === "chromeos" || screen.kind === "windows7"
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: 4
            width: 16; height: 7; radius: screen.kind === "chromeos" ? 3.5 : 1
            color: screen.icon
        }
    }
    // floating dock on the left (Ubuntu), centred below the top bar, the app grid at its end
    Rectangle {
        visible: screen.kind === "ubuntu"
        x: 4
        y: topBar.y + topBar.height + (parent.height - topBar.y - topBar.height - height) / 2
        width: 12; height: dockColumn.height + 6
        radius: 5; color: screen.bar
        Column {
            id: dockColumn
            anchors.centerIn: parent
            spacing: 3
            Repeater {
                model: 4
                Rectangle {
                    required property int index
                    width: 7; height: 7; radius: 2
                    color: index === 3 ? screen.dot : screen.icon
                }
            }
        }
    }
}
