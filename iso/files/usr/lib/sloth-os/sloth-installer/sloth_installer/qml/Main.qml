// Sloth OS telepítő: nyelv -> billentyűzet és időzóna -> lemez -> megerősítés -> telepítés -> kész.
// Az adatok a Python oldali `installer` objektumból jönnek, a szövegek a fordításokból
// (sloth_installer/translations/<nyelv>.json) a t() függvényen keresztül.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: t("app.title")
    visible: true
    visibility: Window.Maximized
    width: Kirigami.Units.gridUnit * 60
    height: Kirigami.Units.gridUnit * 40
    minimumWidth: Kirigami.Units.gridUnit * 36
    minimumHeight: Kirigami.Units.gridUnit * 28
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    readonly property int contentWidth: Math.min(width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 40)
    readonly property var pages: ["welcome", "region", "disk", "confirm", "install", "done", "error"]

    readonly property var strings: installer.strings
    function t(key, args) {
        let text = root.strings[key];
        if (text === undefined)
            return key;
        if (args)
            for (const k in args)
                text = text.split("{" + k + "}").join(args[k]);
        return text;
    }

    // Telepítés közben ne lehessen bezárni
    onClosing: close => close.accepted = installer.page !== "install"

    pageStack.initialPage: Kirigami.Page {
        padding: 0
        globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None

        StackLayout {
            anchors.fill: parent
            currentIndex: root.pages.indexOf(installer.page)

            // --- Üdvözlés és nyelv -------------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: root.contentWidth
                    spacing: Kirigami.Units.largeSpacing * 2
                    Image {
                        Layout.alignment: Qt.AlignHCenter
                        source: "file:///usr/share/sloth-os/logo/sloth-logo.svg"
                        sourceSize.width: Kirigami.Units.gridUnit * 9
                        sourceSize.height: Kirigami.Units.gridUnit * 9
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        level: 1
                        text: root.t("welcome.heading")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: root.t("welcome.text")
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "preferences-desktop-locale"
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }
                        QQC2.ComboBox {
                            Accessible.name: root.t("welcome.language")
                            implicitWidth: Kirigami.Units.gridUnit * 14
                            model: installer.languages
                            textRole: "name"
                            valueRole: "code"
                            currentIndex: count > 0 ? indexOfValue(installer.language) : -1
                            onActivated: installer.setLanguage(currentValue)
                        }
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Button {
                            text: root.t("welcome.try")
                            icon.name: "computer"
                            onClicked: installer.quit()
                        }
                        QQC2.Button {
                            text: root.t("welcome.install")
                            icon.name: "go-next"
                            highlighted: true
                            onClicked: installer.next()
                        }
                    }
                }
            }

            // --- Billentyűzet és időzóna ---------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 28)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignHCenter
                        source: "preferences-desktop-keyboard"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("region.heading")
                    }
                    Kirigami.FormLayout {
                        Layout.fillWidth: true
                        QQC2.ComboBox {
                            Kirigami.FormData.label: root.t("region.keyboard")
                            Layout.fillWidth: true
                            model: installer.keyboards
                            textRole: "name"
                            valueRole: "id"
                            currentIndex: count > 0 ? indexOfValue(installer.keyboard) : -1
                            onActivated: installer.setKeyboard(currentValue)
                        }
                        QQC2.TextField {
                            Kirigami.FormData.label: root.t("region.try_keyboard")
                            Layout.fillWidth: true
                            placeholderText: root.t("region.try_keyboard_hint")
                        }
                        QQC2.ComboBox {
                            Kirigami.FormData.label: root.t("region.timezone")
                            Layout.fillWidth: true
                            model: installer.timezones
                            textRole: "name"
                            valueRole: "id"
                            currentIndex: count > 0 ? indexOfValue(installer.timezone) : -1
                            onActivated: installer.setTimezone(currentValue)
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: root.t("region.note")
                    }
                    NavRow {}
                }
            }

            // --- Lemez kiválasztása ----------------------------------------------------
            ColumnLayout {
                spacing: 0
                QQC2.ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentWidth: availableWidth
                    ColumnLayout {
                        x: (parent.width - width) / 2
                        width: root.contentWidth
                        spacing: Kirigami.Units.largeSpacing * 2
                        Item { implicitHeight: Kirigami.Units.gridUnit * 2 }
                        Kirigami.Icon {
                            Layout.alignment: Qt.AlignHCenter
                            source: "drive-harddisk"
                            implicitWidth: Kirigami.Units.iconSizes.huge
                            implicitHeight: Kirigami.Units.iconSizes.huge
                        }
                        Kirigami.Heading {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            text: root.t("disk.heading")
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: root.t("disk.text")
                        }
                        Kirigami.PlaceholderMessage {
                            Layout.fillWidth: true
                            visible: installer.disks.length === 0
                            icon.name: "drive-harddisk"
                            text: root.t("disk.none")
                            helpfulAction: Kirigami.Action {
                                text: root.t("disk.refresh")
                                icon.name: "view-refresh"
                                onTriggered: installer.refreshDisks()
                            }
                        }
                        Repeater {
                            model: installer.disks
                            delegate: QQC2.AbstractButton {
                                id: diskCard
                                required property var modelData
                                readonly property bool chosen: installer.disk === modelData.path
                                Layout.fillWidth: true
                                implicitHeight: diskRow.implicitHeight + Kirigami.Units.largeSpacing * 2
                                enabled: !modelData.tooSmall
                                onClicked: installer.selectDisk(modelData.path)
                                Accessible.name: modelData.model
                                background: Rectangle {
                                    radius: Kirigami.Units.cornerRadius
                                    color: diskCard.chosen ? Qt.alpha(Kirigami.Theme.highlightColor, 0.35)
                                         : diskCard.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.08)
                                         : Qt.alpha(Kirigami.Theme.textColor, 0.03)
                                    border.width: diskCard.chosen ? 3 : 1
                                    border.color: diskCard.chosen ? Kirigami.Theme.highlightColor
                                                                  : Qt.alpha(Kirigami.Theme.textColor, 0.15)
                                }
                                contentItem: RowLayout {
                                    id: diskRow
                                    spacing: Kirigami.Units.largeSpacing
                                    opacity: diskCard.enabled ? 1 : 0.5
                                    Kirigami.Icon {
                                        Layout.leftMargin: Kirigami.Units.largeSpacing
                                        source: diskCard.modelData.removable ? "drive-removable-media-usb" : "drive-harddisk"
                                        implicitWidth: Kirigami.Units.iconSizes.large
                                        implicitHeight: Kirigami.Units.iconSizes.large
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 0
                                        QQC2.Label {
                                            Layout.fillWidth: true
                                            font.bold: true
                                            elide: Text.ElideRight
                                            text: diskCard.modelData.model + "  ·  " + diskCard.modelData.sizeText
                                        }
                                        QQC2.Label {
                                            Layout.fillWidth: true
                                            wrapMode: Text.Wrap
                                            opacity: 0.75
                                            text: diskCard.modelData.tooSmall ? root.t("disk.too_small")
                                                  : root.t("disk.contents." + diskCard.modelData.contents)
                                                    + (diskCard.modelData.partitionNames.length
                                                       ? " (" + diskCard.modelData.partitionNames.join(", ") + ")" : "")
                                        }
                                        QQC2.Label {
                                            Layout.fillWidth: true
                                            visible: !diskCard.modelData.tooSmall && (diskCard.modelData.removable || diskCard.modelData.small)
                                            wrapMode: Text.Wrap
                                            color: Kirigami.Theme.neutralTextColor
                                            font: Kirigami.Theme.smallFont
                                            text: diskCard.modelData.removable ? root.t("disk.removable") : root.t("disk.small")
                                        }
                                    }
                                    QQC2.RadioButton {
                                        Layout.rightMargin: Kirigami.Units.largeSpacing
                                        checked: diskCard.chosen
                                        enabled: diskCard.enabled
                                        onClicked: installer.selectDisk(diskCard.modelData.path)
                                        Accessible.name: diskCard.modelData.model
                                    }
                                }
                            }
                        }
                        Item { implicitHeight: Kirigami.Units.gridUnit }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: diskNav.implicitHeight + Kirigami.Units.largeSpacing * 2
                    color: Kirigami.Theme.alternateBackgroundColor
                    NavRow {
                        id: diskNav
                        anchors.centerIn: parent
                        nextEnabled: installer.disk !== ""
                    }
                }
            }

            // --- Megerősítés ---------------------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 30)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignHCenter
                        source: "dialog-warning"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("confirm.heading")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("confirm.text", { disk: (installer.diskInfo.model || "") + " (" + (installer.diskInfo.sizeText || "") + ")" })
                    }
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        visible: installer.diskInfo.contents === "windows"
                        type: Kirigami.MessageType.Warning
                        text: root.t("confirm.windows")
                    }
                    QQC2.CheckBox {
                        Layout.alignment: Qt.AlignHCenter
                        text: root.t("confirm.checkbox")
                        checked: installer.confirmed
                        onToggled: installer.setConfirmed(checked)
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Button { text: root.t("nav.back"); icon.name: "go-previous"; onClicked: installer.back() }
                        QQC2.Button {
                            text: root.t("confirm.install")
                            icon.name: "run-install"
                            highlighted: true
                            enabled: installer.confirmed
                            onClicked: installer.install()
                        }
                    }
                }
            }

            // --- Telepítés -----------------------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 30)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Image {
                        Layout.alignment: Qt.AlignHCenter
                        source: "file:///usr/share/sloth-os/logo/sloth-logo.svg"
                        sourceSize.width: Kirigami.Units.gridUnit * 7
                        sourceSize.height: Kirigami.Units.gridUnit * 7
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        level: 2
                        text: installer.statusText
                    }
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: installer.progress
                        indeterminate: installer.progress === 0
                    }
                    QQC2.Label {
                        Layout.alignment: Qt.AlignHCenter
                        opacity: 0.7
                        text: installer.progress + "%"
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.6
                        text: root.t("install.note")
                    }
                }
            }

            // --- Kész ------------------------------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 30)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Image {
                        Layout.alignment: Qt.AlignHCenter
                        source: "file:///usr/share/sloth-os/logo/sloth-logo.svg"
                        sourceSize.width: Kirigami.Units.gridUnit * 8
                        sourceSize.height: Kirigami.Units.gridUnit * 8
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("done.heading")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("done.text")
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignHCenter
                        text: root.t("done.reboot")
                        icon.name: "system-reboot"
                        highlighted: true
                        onClicked: installer.reboot()
                    }
                }
            }

            // --- Hiba --------------------------------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 30)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignHCenter
                        source: "dialog-error"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("error.heading")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: installer.errorText
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: root.t("error.log_hint")
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignHCenter
                        text: root.t("error.retry")
                        icon.name: "view-refresh"
                        onClicked: installer.retry()
                    }
                }
            }
        }
    }

    // Vissza / Tovább gombsor a lépések alján
    component NavRow: RowLayout {
        id: nav
        property bool nextEnabled: true
        Layout.alignment: Qt.AlignHCenter
        spacing: Kirigami.Units.largeSpacing
        QQC2.Button { text: root.t("nav.back"); icon.name: "go-previous"; onClicked: installer.back() }
        QQC2.Button {
            text: root.t("nav.next")
            icon.name: "go-next"
            highlighted: true
            enabled: nav.nextEnabled
            onClicked: installer.next()
        }
    }
}
