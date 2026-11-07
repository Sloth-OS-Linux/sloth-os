// Accessibility: text size, pointer, contrast, motion, screen reader, magnifier, sticky keys (accessibility.py).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Accessibility")

    actions: [
        Kirigami.Action {
            text: L.t("More settings")
            icon.name: "preferences-desktop-accessibility"
            onTriggered: accessibility.openKdeSettings()
        }
    ]

    // One row: a title, a sentence under it, and a switch on the right
    component SwitchRow: RowLayout {
        id: row
        property string title
        property string description
        property bool on
        signal toggled(bool checked)
        Layout.fillWidth: true
        spacing: Kirigami.Units.largeSpacing
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; font.bold: true; text: row.title }
            QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; opacity: 0.75; text: row.description }
        }
        QQC2.Switch {
            checked: row.on
            onToggled: { row.toggled(checked); checked = Qt.binding(() => row.on) }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("Make the computer easier to see, hear and use. Every change works at once and stays after a restart.")
        }

        // --- Seeing ------------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Seeing") }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        QQC2.Label { Layout.fillWidth: true; font.bold: true; text: L.t("Text size") }
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; opacity: 0.75; text: L.t("Bigger text in menus, windows and apps. Some apps show it after they are opened again.") }
                    }
                    QQC2.ComboBox {
                        model: accessibility.textScales.map(p => p + " %")
                        currentIndex: Math.max(0, accessibility.textScales.indexOf(accessibility.textScale))
                        onActivated: (index) => {
                            accessibility.setTextScale(accessibility.textScales[index])
                            currentIndex = Qt.binding(() => Math.max(0, accessibility.textScales.indexOf(accessibility.textScale)))
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        QQC2.Label { Layout.fillWidth: true; font.bold: true; text: L.t("Mouse pointer size") }
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; opacity: 0.75; text: L.t("A bigger pointer is easier to find on the screen.") }
                    }
                    QQC2.ComboBox {
                        readonly property var labels: [L.t("Normal"), L.t("Large"), L.t("Extra large")]
                        model: labels
                        currentIndex: Math.max(0, accessibility.cursorSizes.indexOf(accessibility.cursorSize))
                        onActivated: (index) => {
                            accessibility.setCursorSize(accessibility.cursorSizes[index])
                            currentIndex = Qt.binding(() => Math.max(0, accessibility.cursorSizes.indexOf(accessibility.cursorSize)))
                        }
                    }
                }
                SwitchRow {
                    title: L.t("High contrast")
                    description: L.t("Black and white with a yellow highlight, the easiest colors to tell apart. Turning it off brings back your color scheme.")
                    on: accessibility.highContrast
                    onToggled: (checked) => accessibility.setHighContrast(checked)
                }
                SwitchRow {
                    title: L.t("Magnifier")
                    description: L.t("Zoom in with the Windows key and +, zoom out with the Windows key and −. The view follows the mouse.")
                    on: accessibility.magnifier
                    onToggled: (checked) => accessibility.setMagnifier(checked)
                }
                SwitchRow {
                    title: L.t("Less motion")
                    description: L.t("Windows and menus open at once, without animations.")
                    on: accessibility.reduceMotion
                    onToggled: (checked) => accessibility.setReduceMotion(checked)
                }
            }
        }

        // --- Hearing and reading -------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Screen reader") }
                SwitchRow {
                    title: L.t("Read the screen aloud")
                    description: L.t("Orca reads out what is on the screen and what you type. It starts by itself at every sign-in until you turn it off here.")
                    on: accessibility.screenReader
                    onToggled: (checked) => accessibility.setScreenReader(checked)
                }
            }
        }

        // --- Keyboard ---------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Keyboard") }
                SwitchRow {
                    title: L.t("Sticky keys")
                    description: L.t("Press Ctrl, Shift or Alt one after another instead of together: Ctrl, then C copies.")
                    on: accessibility.stickyKeys
                    onToggled: (checked) => accessibility.setStickyKeys(checked)
                }
            }
        }
    }

    Component.onCompleted: accessibility.refresh()
}
