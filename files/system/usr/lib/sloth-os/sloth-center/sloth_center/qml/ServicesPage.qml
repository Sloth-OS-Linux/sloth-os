// Services: the common ones with understandable names and switches; an advanced list of all running ones.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Services")

    actions: [
        Kirigami.Action {
            text: L.t("Refresh")
            icon.name: "view-refresh"
            onTriggered: services.refresh()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: services.errorText !== ""
            text: services.errorText
        }

        Kirigami.Heading { level: 3; text: L.t("Common services") }

        Repeater {
            model: services.common
            delegate: Kirigami.AbstractCard {
                id: card
                required property var modelData
                Layout.fillWidth: true
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        QQC2.Label { text: card.modelData.name; font.bold: true }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.7
                            text: card.modelData.description
                        }
                    }
                    QQC2.BusyIndicator {
                        visible: services.busyUnit === card.modelData.unit
                        running: visible
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                    }
                    QQC2.Switch {
                        checked: card.modelData.enabled
                        enabled: !card.modelData.locked && services.busyUnit === ""
                        onToggled: services.setEnabled(card.modelData.unit, checked)
                    }
                }
            }
        }

        QQC2.CheckBox {
            id: showAll
            text: L.t("Show all running services (advanced)")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: showAll.checked
            type: Kirigami.MessageType.Warning
            text: L.t("Stopping a service can keep part of the system from working properly. After a restart everything goes back to normal.")
        }

        Repeater {
            model: showAll.checked ? services.allServices : []
            delegate: RowLayout {
                id: row
                required property var modelData
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: row.modelData.description }
                    QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; opacity: 0.6; font: Kirigami.Theme.smallFont; text: row.modelData.unit }
                }
                QQC2.Label {
                    opacity: 0.7
                    text: row.modelData.active ? L.t("Running") : L.t("Stopped")
                }
                QQC2.Button {
                    enabled: services.busyUnit === ""
                    text: row.modelData.active ? L.t("Stop") : L.t("Start")
                    icon.name: row.modelData.active ? "media-playback-stop" : "media-playback-start"
                    onClicked: services.setRunning(row.modelData.unit, !row.modelData.active)
                }
            }
        }

        Kirigami.Separator { Layout.fillWidth: true; visible: showUser.checked }

        QQC2.CheckBox {
            id: showUser
            text: L.t("Show my own services (advanced)")
        }

        QQC2.Label {
            Layout.fillWidth: true
            visible: showUser.checked
            wrapMode: Text.Wrap
            opacity: 0.7
            text: L.t("These only run in your account, after you sign in. Changing them does not need a password.")
        }

        Repeater {
            model: showUser.checked ? services.userServices : []
            delegate: RowLayout {
                id: userRow
                required property var modelData
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: userRow.modelData.description }
                    QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; opacity: 0.6; font: Kirigami.Theme.smallFont; text: userRow.modelData.unit }
                }
                QQC2.Label {
                    opacity: 0.7
                    text: userRow.modelData.active ? L.t("Running") : L.t("Stopped")
                }
                Kirigami.Icon {
                    visible: userRow.modelData.protected
                    source: "object-locked"
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: Kirigami.Units.iconSizes.small
                    QQC2.ToolTip.visible: lockArea.containsMouse
                    QQC2.ToolTip.text: L.t("The system needs this to work, so it cannot be changed.")
                    MouseArea { id: lockArea; anchors.fill: parent; hoverEnabled: true }
                }
                QQC2.Button {
                    visible: !userRow.modelData.protected
                    enabled: services.busyUnit === ""
                    text: userRow.modelData.active ? L.t("Stop") : L.t("Start")
                    icon.name: userRow.modelData.active ? "media-playback-stop" : "media-playback-start"
                    onClicked: services.setUserRunning(userRow.modelData.unit, !userRow.modelData.active)
                }
                QQC2.Switch {
                    visible: userRow.modelData.switchable
                    checked: userRow.modelData.enabled
                    enabled: services.busyUnit === ""
                    onToggled: services.setUserEnabled(userRow.modelData.unit, checked)
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.text: L.t("Start at sign-in")
                }
            }
        }
    }
}
