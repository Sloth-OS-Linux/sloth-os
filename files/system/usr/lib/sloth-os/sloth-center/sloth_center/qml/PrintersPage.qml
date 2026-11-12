// Printers and scanners: the ones found by themselves, a test page, the default printer, scanning (printers.py).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Printers and scanners")

    actions: [
        Kirigami.Action {
            text: L.t("Look again")
            icon.name: "view-refresh"
            enabled: !printers.busy
            onTriggered: printers.refresh()
        }
    ]

    Component.onCompleted: printers.refresh()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("Most printers and scanners work without installing anything: turn them on and connect them with a USB cable or to the same Wi-Fi network, and they show up here.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: printers.message !== ""
            type: Kirigami.MessageType.Information
            text: printers.message
            showCloseButton: true
        }

        RowLayout {
            visible: printers.busy
            QQC2.BusyIndicator { running: parent.visible }
            QQC2.Label { text: L.t("Looking for printers and scanners…") }
        }

        // --- Printers ---------------------------------------------------------------------------------------
        Kirigami.Heading { level: 3; text: L.t("Printers") }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            visible: !printers.busy && printers.printers.length === 0
            text: L.t("No printer found. Check that it is on and connected, then press Look again. An older printer may need to be added by hand.")
        }
        Repeater {
            model: printers.printers
            delegate: Kirigami.AbstractCard {
                id: printerCard
                required property var modelData
                Layout.fillWidth: true
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: "printer"
                        implicitWidth: Kirigami.Units.iconSizes.medium
                        implicitHeight: Kirigami.Units.iconSizes.medium
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            font.bold: true
                            text: printerCard.modelData.label
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.7
                            text: printerCard.modelData.stateText
                                  + (printerCard.modelData.isDefault ? " · " + L.t("Used by default") : "")
                        }
                    }
                    QQC2.Button {
                        text: L.t("Test page")
                        icon.name: "document-print"
                        onClicked: printers.printTestPage(printerCard.modelData.name)
                    }
                    QQC2.Button {
                        visible: !printerCard.modelData.isDefault
                        text: L.t("Use by default")
                        icon.name: "starred-symbolic"
                        onClicked: printers.setDefault(printerCard.modelData.name)
                    }
                    QQC2.Button {
                        text: L.t("Print queue")
                        icon.name: "view-list-details"
                        onClicked: printers.openQueue(printerCard.modelData.name)
                    }
                }
            }
        }
        QQC2.Button {
            text: L.t("Add a printer by hand…")
            icon.name: "list-add"
            onClicked: printers.addPrinter()
        }

        // --- Scanners ---------------------------------------------------------------------------------------
        Kirigami.Heading { level: 3; text: L.t("Scanners") }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            visible: !printers.busy && printers.scanners.length === 0
            text: L.t("No scanner found. Many printers can scan too: turn it on, then press Look again.")
        }
        Repeater {
            model: printers.scanners
            delegate: QQC2.Label {
                required property var modelData
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: "• " + modelData.label
            }
        }
        QQC2.Button {
            text: L.t("Scan a document")
            icon.name: "document-scan"
            onClicked: printers.scan()
        }
    }
}
