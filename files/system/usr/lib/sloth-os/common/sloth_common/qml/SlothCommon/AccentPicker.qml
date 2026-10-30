// "Your own color" (sloth_common.appearance): the scheme's own, a few suggested colors, or any color from a picker.
// Sloth Welcome and Sloth Center show the same one; the texts come from the tool (each has its own translations).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import org.kde.kirigami as Kirigami

Flow {
    id: picker
    property var colors: []          // "#rrggbb" suggestions
    property string current: ""      // "" = the scheme's own color
    property string ownText: ""      // "The scheme's own"
    property string otherText: ""    // "Other color…"
    signal picked(string color)

    readonly property int dot: Kirigami.Units.gridUnit * 2
    readonly property bool custom: current !== "" && colors.indexOf(current.toLowerCase()) < 0
    spacing: Kirigami.Units.largeSpacing

    QQC2.Button {
        height: picker.dot
        text: picker.ownText
        checked: picker.current === ""   // not checkable: a click must not break the binding
        onClicked: picker.picked("")
    }
    Repeater {
        model: picker.colors
        delegate: QQC2.AbstractButton {
            id: swatch
            required property string modelData
            readonly property bool selected: picker.current.toLowerCase() === modelData
            width: picker.dot
            height: picker.dot
            Accessible.name: modelData
            onClicked: picker.picked(modelData)
            contentItem: Item {}
            background: Rectangle {
                radius: width / 2
                color: swatch.modelData
                border.width: swatch.selected ? 3 : (swatch.hovered ? 2 : 0)
                border.color: Kirigami.Theme.textColor
                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: parent.width / 2
                    height: width
                    visible: swatch.selected
                    source: "checkmark"
                    color: "white"
                }
            }
        }
    }
    QQC2.Button {
        height: picker.dot
        text: picker.otherText
        icon.name: "color-picker"
        checked: picker.custom
        onClicked: {
            dialog.selectedColor = picker.current || picker.colors[0];
            dialog.open();
        }
        // the color chosen in the picker, next to the button
        Rectangle {
            visible: picker.custom
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.right
            anchors.leftMargin: Kirigami.Units.smallSpacing
            width: picker.dot * 0.6
            height: width
            radius: width / 2
            color: picker.custom ? picker.current : "transparent"
            border.width: 1
            border.color: Qt.alpha(Kirigami.Theme.textColor, 0.4)
        }
    }
    ColorDialog {
        id: dialog
        onAccepted: picker.picked(String(selectedColor).slice(0, 7))
    }
}
