// Feedback: a bug, an idea or something else for the developers (feedback.py). No GitHub account needed.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Feedback")

    property string kind: "bug"

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: feedback.result !== ""
            type: feedback.result === "sent" ? Kirigami.MessageType.Positive : Kirigami.MessageType.Warning
            text: feedback.result === "sent"
                  ? L.tf("Thank you! We got it. Your report number is #{number}.", { number: feedback.number })
                  : feedback.result === "rate"
                    ? L.t("A lot of feedback has already been sent from this computer today. You can send more tomorrow.")
                    : feedback.result === "network"
                      ? L.t("Couldn't send it: there is no internet connection. Please try again later.")
                      : L.t("Couldn't send it. Please try again later.")
        }

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: L.t("Something not working, or have an idea? Describe it in your own words and we'll send it to the Sloth OS developers.")
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            QQC2.Label { text: L.t("What is it about?"); font.bold: true }
            Repeater {
                model: [
                    { value: "bug", text: L.t("Problem: something doesn't work the way it should") },
                    { value: "idea", text: L.t("Idea: something missing or that could be better") },
                    { value: "other", text: L.t("Other") }
                ]
                delegate: QQC2.RadioButton {
                    required property var modelData
                    text: modelData.text
                    checked: page.kind === modelData.value
                    onToggled: page.kind = modelData.value
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            QQC2.Label {
                text: page.kind === "bug" ? L.t("What happened, and what were you doing before?") : L.t("Describe it in a few sentences")
                font.bold: true
            }
            QQC2.TextArea {
                id: textField
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 10
                wrapMode: TextEdit.Wrap
                enabled: !feedback.busy
                placeholderText: page.kind === "bug"
                                 ? L.t("For example: I started Battle.net, but it closed after a minute.")
                                 : ""
                onTextChanged: if (feedback.result === "sent") feedback.reset()
            }
        }

        QQC2.CheckBox {
            id: attachLog
            Layout.fillWidth: true
            checked: page.kind === "bug"
            enabled: !feedback.busy
            text: L.t("Attach computer information and log (helps find the problem)")
        }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.7
            text: L.t("The information is not public: only the developers can see it, and it is deleted after 30 days. Personal details are hidden in it, and you can see exactly what is sent. Your description is not public either: only the developers can see it.")
        }
        QQC2.Button {
            visible: attachLog.checked
            enabled: !feedback.busy
            text: L.t("Show what is sent")
            icon.name: "document-preview"
            onClicked: {
                previewDialog.open()
                if (feedback.preview === "")
                    feedback.prepare()
            }
        }

        RowLayout {
            QQC2.Button {
                text: feedback.busy ? L.t("Sending…") : L.t("Send")
                icon.name: "mail-send"
                enabled: !feedback.busy && textField.text.trim().length >= 10
                onClicked: feedback.send(page.kind, textField.text, attachLog.checked)
            }
            QQC2.BusyIndicator {
                visible: feedback.busy
                running: visible
                implicitHeight: Kirigami.Units.iconSizes.medium
            }
        }

        // Support (Ko-fi): a quiet link, it asks for nothing; the address is in the text too, in case there is no browser
        Kirigami.Separator { Layout.fillWidth: true; Layout.topMargin: Kirigami.Units.largeSpacing }
        QQC2.Label { text: L.t("Support Sloth OS"); font.bold: true }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.7
            text: L.t("Sloth OS is free and made in spare time. If you like it, you can support its development with a beer: ko-fi.com/slothos")
        }
        QQC2.Button {
            text: L.t("Support on Ko-fi")
            icon.name: "emblem-favorite"
            onClicked: Qt.openUrlExternally("https://ko-fi.com/slothos")
        }
    }

    // The computer's information exactly as it is sent, personal details already hidden (diagnostics.py)
    Kirigami.Dialog {
        id: previewDialog
        objectName: "previewDialog"
        title: L.t("What is sent")
        preferredWidth: Math.min(page.width - Kirigami.Units.gridUnit * 2, Kirigami.Units.gridUnit * 50)
        preferredHeight: Math.min(page.height - Kirigami.Units.gridUnit * 2, Kirigami.Units.gridUnit * 36)
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Close")
                icon.name: "dialog-close"
                onTriggered: previewDialog.close()
            }
        ]
        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: L.t("Your name, user name, computer name, network names, network and e-mail addresses and serial numbers are replaced with placeholders such as <user>.")
                textFormat: Text.PlainText
            }
            RowLayout {
                visible: feedback.preparing
                QQC2.BusyIndicator { running: parent.visible }
                QQC2.Label { text: L.t("Collecting the information…") }
            }
            QQC2.ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 26
                visible: !feedback.preparing
                QQC2.TextArea {
                    readOnly: true
                    text: feedback.preview
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.NoWrap
                    font.family: "monospace"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }
        }
    }
}
