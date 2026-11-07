// Power and battery: the battery, the power mode, screen and sleep timers, lid and power button (power.py).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Power and battery")

    actions: [
        Kirigami.Action {
            text: L.t("More settings")
            icon.name: "preferences-system-power-management"
            onTriggered: power.openKdeSettings()
        }
    ]

    function minutesText(m) {
        if (m < 0) return L.t("As KDE sets it");
        if (m === 0) return L.t("Never");
        const names = { 2: L.t("2 minutes"), 5: L.t("5 minutes"), 10: L.t("10 minutes"), 15: L.t("15 minutes"),
                        30: L.t("30 minutes"), 60: L.t("1 hour"), 120: L.t("2 hours") };
        return names[m] || "";
    }
    function modeText(mode) {
        return { "power-saver": L.t("Power saver"), "balanced": L.t("Balanced"), "performance": L.t("Best performance") }[mode] || mode;
    }
    function actionText(a) {
        return { 0: L.t("Do nothing"), 1: L.t("Sleep"), 8: L.t("Shut down"), 16: L.t("Ask what to do"),
                 64: L.t("Turn off the screen") }[a] || "";
    }
    function timeText(minutes) {
        const h = Math.floor(minutes / 60), m = minutes % 60;
        return h > 0 ? L.tf("{h} h {m} min", { h: h, m: m }) : L.tf("{m} min", { m: m });
    }

    // A label on the left, a list of choices on the right
    component ChoiceRow: RowLayout {
        id: row
        property string label
        property var choices: []
        property var current
        property var textOf
        signal chosen(var value)
        Layout.fillWidth: true
        spacing: Kirigami.Units.largeSpacing
        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: row.label }
        QQC2.ComboBox {
            model: row.choices.map(c => row.textOf(c))
            currentIndex: Math.max(0, row.choices.indexOf(row.current))
            onActivated: (index) => {
                row.chosen(row.choices[index])
                currentIndex = Qt.binding(() => Math.max(0, row.choices.indexOf(row.current)))
            }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        // --- Battery -------------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: power.hasBattery
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: power.charging ? "battery-charging" : "battery"
                        implicitWidth: Kirigami.Units.iconSizes.large
                        implicitHeight: Kirigami.Units.iconSizes.large
                    }
                    ColumnLayout {
                        spacing: 0
                        Kirigami.Heading { level: 2; text: power.batteryPercent + " %" }
                        QQC2.Label {
                            opacity: 0.8
                            text: power.fullyCharged ? L.t("Fully charged")
                                : power.charging ? (power.minutesLeft > 0 ? L.tf("Charging, full in {time}", { time: page.timeText(power.minutesLeft) }) : L.t("Charging"))
                                : (power.minutesLeft > 0 ? L.tf("About {time} left", { time: page.timeText(power.minutesLeft) }) : L.t("On battery"))
                        }
                    }
                }
                QQC2.ProgressBar { Layout.fillWidth: true; from: 0; to: 100; value: power.batteryPercent }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: power.batteryHealth > 0
                    opacity: 0.8
                    text: L.tf("Battery health: {n} %. It holds this much of what it held when it was new.", { n: power.batteryHealth })
                        + (power.batteryHealth < 70 ? " " + L.t("Below 70% a battery runs down noticeably faster; it may be time to replace it.") : "")
                }
            }
        }

        // --- Power mode ----------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: power.powerModes.length > 0
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Power mode") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Power saver makes the battery last longer, best performance gives games and heavy work the most speed.")
                }
                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: power.powerModes
                        delegate: QQC2.Button {
                            required property string modelData
                            text: page.modeText(modelData)
                            checkable: true
                            checked: power.powerMode === modelData
                            onClicked: { power.setPowerMode(modelData); checked = Qt.binding(() => power.powerMode === modelData) }
                        }
                    }
                }
            }
        }

        // --- Screen and sleep ----------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Screen and sleep") }
                ChoiceRow {
                    label: power.hasBattery ? L.t("Turn off the screen after (plugged in)") : L.t("Turn off the screen after")
                    choices: power.screenChoices; current: power.screenOffAc; textOf: page.minutesText
                    onChosen: (v) => power.setScreenOff("AC", v)
                }
                ChoiceRow {
                    visible: power.hasBattery
                    label: L.t("Turn off the screen after (on battery)")
                    choices: power.screenChoices; current: power.screenOffBattery; textOf: page.minutesText
                    onChosen: (v) => power.setScreenOff("Battery", v)
                }
                ChoiceRow {
                    label: power.hasBattery ? L.t("Go to sleep after (plugged in)") : L.t("Go to sleep after")
                    choices: power.sleepChoices; current: power.sleepAc; textOf: page.minutesText
                    onChosen: (v) => power.setSleepAfter("AC", v)
                }
                ChoiceRow {
                    visible: power.hasBattery
                    label: L.t("Go to sleep after (on battery)")
                    choices: power.sleepChoices; current: power.sleepBattery; textOf: page.minutesText
                    onChosen: (v) => power.setSleepAfter("Battery", v)
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("While a video or a game runs full screen, the screen stays on and the computer stays awake.")
                }
            }
        }

        // --- Buttons and lid -----------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: power.hasLid ? L.t("Lid and power button") : L.t("Power button") }
                ChoiceRow {
                    visible: power.hasLid
                    label: L.t("When I close the lid")
                    choices: power.lidChoices; current: power.lidAction; textOf: page.actionText
                    onChosen: (v) => power.setLidAction(v)
                }
                ChoiceRow {
                    label: L.t("When I press the power button")
                    choices: power.buttonChoices; current: power.buttonAction; textOf: page.actionText
                    onChosen: (v) => power.setButtonAction(v)
                }
            }
        }
    }

    Component.onCompleted: power.refresh()
}
