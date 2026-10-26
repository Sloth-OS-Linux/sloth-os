// A small drawing of a taskbar layout (sloth_common.appearance): Sloth Welcome and Sloth Center show the same one
import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    id: screen
    property string kind: ""
    property bool current: false
    readonly property bool topBar: kind === "mac" || kind === "ubuntu"
    readonly property color bar: Qt.alpha(Kirigami.Theme.textColor, 0.35)
    readonly property color dot: Kirigami.Theme.highlightColor

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
    // bottom taskbar / dock
    Rectangle {
        visible: screen.kind !== "ubuntu"
        anchors.bottom: parent.bottom
        anchors.bottomMargin: screen.kind === "mac" ? 8 : 3
        x: screen.kind === "mac" ? parent.width * 0.3 : 3
        width: screen.kind === "mac" ? parent.width * 0.4 : parent.width - 6
        height: 12; radius: screen.kind === "mac" ? 5 : 2
        color: screen.bar
        Row {
            anchors.verticalCenter: parent.verticalCenter
            x: screen.kind === "windows10" ? 4 : (parent.width - width) / 2
            spacing: 3
            Repeater {
                model: 4
                Rectangle {
                    required property int index
                    width: 7; height: 7; radius: 2
                    color: index === 0 && screen.kind !== "mac" ? screen.dot : Qt.alpha(Kirigami.Theme.backgroundColor, 0.9)
                }
            }
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
                    color: index === 3 ? screen.dot : Qt.alpha(Kirigami.Theme.backgroundColor, 0.9)
                }
            }
        }
    }
}
