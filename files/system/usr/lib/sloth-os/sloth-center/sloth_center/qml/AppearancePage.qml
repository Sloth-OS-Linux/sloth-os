// Appearance: the color scheme and the taskbar layout, the same ones as in Sloth Welcome (appearance.py)
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import SlothCommon
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Appearance")

    readonly property int cardWidth: Kirigami.Units.gridUnit * 10

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: appearance.errorText !== ""
            text: appearance.errorText
        }

        Kirigami.Heading {
            level: 2
            text: L.t("Taskbar")
        }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("The same layouts as in the welcome wizard. Click one to see it right away; the apps pinned to the taskbar stay.")
        }
        Flow {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Repeater {
                model: appearance.layouts
                delegate: QQC2.AbstractButton {
                    id: layoutCard
                    required property var modelData
                    readonly property bool current: appearance.currentLayout === modelData.id
                    width: page.cardWidth
                    height: Kirigami.Units.gridUnit * 8
                    onClicked: appearance.setLayout(modelData.id)
                    Accessible.name: modelData.name
                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing
                        LayoutPreview {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            kind: layoutCard.modelData.id
                            current: layoutCard.current
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            text: layoutCard.modelData.name
                            font.bold: layoutCard.current
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            opacity: 0.7
                            font: Kirigami.Theme.smallFont
                            text: layoutCard.modelData.description
                        }
                    }
                }
            }
        }

        Kirigami.Heading {
            level: 2
            text: L.t("Colors")
        }
        Flow {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Repeater {
                model: appearance.schemes
                delegate: QQC2.AbstractButton {
                    id: schemeCard
                    required property var modelData
                    readonly property bool current: appearance.currentScheme === modelData.id
                    width: page.cardWidth
                    height: Kirigami.Units.gridUnit * 6
                    onClicked: appearance.setScheme(modelData.id)
                    Accessible.name: modelData.name
                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: Kirigami.Units.cornerRadius
                            color: schemeCard.modelData.colors[0]
                            border.width: schemeCard.current ? 3 : 1
                            border.color: schemeCard.current ? Kirigami.Theme.highlightColor : Qt.rgba(0.5, 0.5, 0.5, 0.4)
                            Rectangle {
                                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Kirigami.Units.largeSpacing }
                                height: Kirigami.Units.gridUnit
                                radius: height / 3
                                color: schemeCard.modelData.colors[1]
                            }
                            Rectangle {
                                x: Kirigami.Units.largeSpacing
                                y: Kirigami.Units.largeSpacing
                                width: parent.width * 0.5
                                height: Kirigami.Units.smallSpacing * 2
                                radius: height / 2
                                color: schemeCard.modelData.colors[2]
                            }
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            text: schemeCard.modelData.name
                            font.bold: schemeCard.current
                        }
                    }
                }
            }
        }

        Kirigami.Heading {
            level: 3
            text: L.t("Highlight color")
        }
        AccentPicker {
            Layout.fillWidth: true
            colors: appearance.accentColors
            current: appearance.currentAccent
            ownText: L.t("The scheme's own")
            otherText: L.t("Other color…")
            onPicked: color => appearance.setAccent(color)
        }
        QQC2.CheckBox {
            text: L.t("Color the window title bars too")
            checked: appearance.titlebarAccent
            onToggled: appearance.setTitlebarAccent(checked)
        }

        QQC2.Button {
            text: L.t("More appearance settings")
            icon.name: "preferences-desktop-theme-global"
            onClicked: appearance.openSystemSettings()
        }
    }
}
