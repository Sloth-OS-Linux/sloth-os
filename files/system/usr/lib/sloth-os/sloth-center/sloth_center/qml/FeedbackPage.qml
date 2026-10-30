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
            text: L.t("The log is not public: only the developers can see it, and it is deleted after 30 days. It may contain your user name and device names, but not your files. Your description is not public either: only the developers can see it.")
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
}
