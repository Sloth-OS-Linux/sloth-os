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
            text: L.t("Make the computer easier to see, hear and use. Your changes stay after a restart.")
        }

        // The text and pointer size show everywhere only after signing in again (seen on the HP, 2026-11-09)
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Information
            visible: accessibility.signOutNeeded
            text: L.t("Sign out and in again to see the new size everywhere.")
            actions: [
                Kirigami.Action {
                    text: L.t("Sign out now")
                    icon.name: "system-log-out"
                    onTriggered: accessibility.signOut()
                }
            ]
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
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; opacity: 0.75; text: L.t("Bigger text in menus, windows and apps. It shows everywhere after you sign out and in again.") }
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
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; opacity: 0.75; text: L.t("A bigger pointer is easier to find on the screen. It shows everywhere after you sign out and in again.") }
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
                    description: L.t("Zoom in and out with the Windows key and + or −, or on a touchpad by pinching with three fingers. The Windows key and 0 brings the normal size back. The view follows the mouse.")
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
