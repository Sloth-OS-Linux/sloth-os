// Visszajelzés: hiba, ötlet vagy egyéb a fejlesztőknek (feedback.py). GitHub-fiók nem kell.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Visszajelzés")

    property string kind: "bug"

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: feedback.result !== ""
            type: feedback.result === "sent" ? Kirigami.MessageType.Positive : Kirigami.MessageType.Warning
            text: feedback.result === "sent"
                  ? L.tf("Köszönjük! Megkaptuk, a bejelentés száma: #{number}.", { number: feedback.number })
                  : feedback.result === "rate"
                    ? L.t("Ma már sok visszajelzés ment erről a gépről. Holnap újra küldhetsz.")
                    : feedback.result === "network"
                      ? L.t("Nem sikerült elküldeni: nincs internetkapcsolat. Próbáld újra később.")
                      : L.t("Nem sikerült elküldeni. Próbáld újra később.")
        }

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: L.t("Valami nem működik, vagy van egy ötleted? Írd le a saját szavaiddal, és elküldjük a Sloth OS fejlesztőinek.")
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            QQC2.Label { text: L.t("Miről szól?"); font.bold: true }
            Repeater {
                model: [
                    { value: "bug", text: L.t("Hiba: valami nem úgy működik, ahogy kellene") },
                    { value: "idea", text: L.t("Ötlet: valami, ami hiányzik vagy jobb lehetne") },
                    { value: "other", text: L.t("Egyéb") }
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
                text: page.kind === "bug" ? L.t("Mi történt, és mit csináltál előtte?") : L.t("Írd le pár mondatban")
                font.bold: true
            }
            QQC2.TextArea {
                id: textField
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 10
                wrapMode: TextEdit.Wrap
                enabled: !feedback.busy
                placeholderText: page.kind === "bug"
                                 ? L.t("Például: elindítottam a Battle.net-et, de egy perc után bezárult.")
                                 : ""
                onTextChanged: if (feedback.result === "sent") feedback.reset()
            }
        }

        QQC2.CheckBox {
            id: attachLog
            Layout.fillWidth: true
            checked: page.kind === "bug"
            enabled: !feedback.busy
            text: L.t("Gépinformáció és napló csatolása (segít megtalálni a hibát)")
        }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.7
            text: L.t("A napló nem nyilvános: csak a fejlesztők látják, és 30 nap után törlődik. Szerepelhet benne a felhasználóneved és az eszközeid neve, a fájljaid nem. A leírásod nyilvános lesz, név nélkül.")
        }

        RowLayout {
            QQC2.Button {
                text: feedback.busy ? L.t("Küldés…") : L.t("Küldés")
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

        // Támogatás (Ko-fi): csendes link, nem kér semmit; a cím a szövegben is ott van, ha nincs böngésző
        Kirigami.Separator { Layout.fillWidth: true; Layout.topMargin: Kirigami.Units.largeSpacing }
        QQC2.Label { text: L.t("Támogasd a Sloth OS-t"); font.bold: true }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.7
            text: L.t("A Sloth OS ingyenes, és szabadidőben készül. Ha tetszik, egy sörrel támogathatod a fejlesztését: ko-fi.com/slothos")
        }
        QQC2.Button {
            text: L.t("Támogatás a Ko-fi-n")
            icon.name: "emblem-favorite"
            onClicked: Qt.openUrlExternally("https://ko-fi.com/slothos")
        }
    }
}
