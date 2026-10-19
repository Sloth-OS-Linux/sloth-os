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
    // Teljes képernyő, mint a Windows telepítője: indításkor ez az első, amit a felhasználó lát
    // (Kipróbálom / Telepítem); az asztal csak a "Kipróbálom" után látszik.
    visibility: Window.FullScreen
    width: Kirigami.Units.gridUnit * 60
    height: Kirigami.Units.gridUnit * 40
    minimumWidth: Kirigami.Units.gridUnit * 36
    minimumHeight: Kirigami.Units.gridUnit * 28
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    readonly property int contentWidth: Math.min(width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 40)
    readonly property var pages: ["welcome", "region", "account", "disk", "confirm", "install", "done", "error"]

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

    // A lemez neve és fajtája, pl. "Samsung SSD 980 · NVMe SSD"
    function diskName(d) {
        if (!d || !d.path)
            return "";
        const kinds = {
            nvme: root.t("disk.kind.nvme"),
            ssd: root.t("disk.kind.ssd"),
            hdd: root.t("disk.kind.hdd"),
            usb: root.t("disk.kind.usb")
        };
        return d.model + (kinds[d.kind] ? "  ·  " + kinds[d.kind] : "");
    }

    // Lapváltáskor a fókusz az elsődleges gombra kerül, hogy billentyűzettel (Enter) is lehessen haladni
    property string shownPage: ""
    Connections {
        target: installer
        // a Python oldalon minden tulajdonság a közös "changed" jelzéssel frissül
        function onChanged() {
            if (installer.page !== root.shownPage) {
                root.shownPage = installer.page;
                focusTimer.restart();
            }
        }
    }
    Timer {
        id: focusTimer
        interval: 50
        onTriggered: {
            const target = {
                welcome: installButton, region: regionNav.nextButton, account: fullNameField, disk: diskNav.nextButton,
                confirm: confirmCheck, done: rebootButton, error: retryButton
            }[installer.page];
            if (target)
                target.forceActiveFocus(Qt.TabFocusReason);
        }
    }
    Component.onCompleted: focusTimer.start()

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
                            popup.popupType: QQC2.Popup.Item
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
                            onClicked: installer.tryLive()
                        }
                        QQC2.Button {
                            id: installButton
                            Keys.onReturnPressed: clicked()
                            Keys.onEnterPressed: clicked()
                            text: root.t("welcome.install")
                            icon.name: "go-next"
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
                            popup.popupType: QQC2.Popup.Item
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
                            popup.popupType: QQC2.Popup.Item
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
                    NavRow { id: regionNav }
                }
            }

            // --- Fiók (első induláskor a telepített rendszer hozza létre) --------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 28)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignHCenter
                        source: "user-identity"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("account.heading")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: root.t("account.text")
                    }
                    Kirigami.FormLayout {
                        Layout.fillWidth: true
                        QQC2.TextField {
                            id: fullNameField
                            Kirigami.FormData.label: root.t("account.fullname")
                            Layout.fillWidth: true
                            placeholderText: root.t("account.fullname_hint")
                            onTextEdited: { installer.setFullName(text); accountError.text = ""; }
                        }
                        QQC2.TextField {
                            Kirigami.FormData.label: root.t("account.username")
                            Layout.fillWidth: true
                            text: installer.username
                            onTextEdited: { installer.setUsername(text); accountError.text = ""; }
                        }
                        // a Kirigami saját „Password” helykitöltője a telepítő nyelvváltását nem követi; a címke elég
                        Kirigami.PasswordField {
                            id: passwordField
                            placeholderText: ""
                            Kirigami.FormData.label: root.t("account.password")
                            Layout.fillWidth: true
                            onTextEdited: accountError.text = ""
                        }
                        Kirigami.PasswordField {
                            id: passwordAgain
                            placeholderText: ""
                            Kirigami.FormData.label: root.t("account.password_again")
                            Layout.fillWidth: true
                            onTextEdited: accountError.text = ""
                            onAccepted: accountNext.clicked()
                        }
                    }
                    Kirigami.InlineMessage {
                        id: accountError
                        Layout.fillWidth: true
                        type: Kirigami.MessageType.Error
                        visible: text !== ""
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: root.t("account.note")
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Button { text: root.t("nav.back"); icon.name: "go-previous"; onClicked: installer.back() }
                        QQC2.Button {
                            id: accountNext
                            text: root.t("nav.next")
                            icon.name: "go-next"
                            Keys.onReturnPressed: clicked()
                            Keys.onEnterPressed: clicked()
                            onClicked: {
                                const err = installer.accountError(passwordField.text, passwordAgain.text);
                                if (err !== "") {
                                    accountError.text = root.t(err);
                                    return;
                                }
                                installer.setPassword(passwordField.text);
                                installer.next();
                            }
                        }
                    }
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
                                Accessible.name: root.diskName(modelData)
                                background: Rectangle {
                                    radius: Kirigami.Units.cornerRadius
                                    color: diskCard.chosen ? Qt.alpha(Kirigami.Theme.highlightColor, 0.35)
                                         : diskCard.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.08)
                                         : Qt.alpha(Kirigami.Theme.textColor, 0.03)
                                    border.width: diskCard.chosen || diskCard.visualFocus ? 3 : 1
                                    border.color: diskCard.chosen || diskCard.visualFocus ? Kirigami.Theme.highlightColor
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
                                            text: root.diskName(diskCard.modelData) + "  ·  " + diskCard.modelData.sizeText
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
                                        focusPolicy: Qt.NoFocus   // a kártya maga kapja a fókuszt
                                        checked: diskCard.chosen
                                        enabled: diskCard.enabled
                                        onClicked: installer.selectDisk(diskCard.modelData.path)
                                        Accessible.name: root.diskName(diskCard.modelData)
                                    }
                                }
                            }
                        }
                        // Windows mellé vagy az egész lemez (csak Windowsos lemeznél)
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: installer.diskInfo.contents === "windows"
                            spacing: Kirigami.Units.largeSpacing
                            RowLayout {
                                visible: installer.besideInfo.state === "probing"
                                Layout.alignment: Qt.AlignHCenter
                                spacing: Kirigami.Units.largeSpacing
                                QQC2.BusyIndicator { running: parent.visible }
                                QQC2.Label { text: root.t("disk.beside.probing") }
                            }
                            QQC2.ButtonGroup { id: besideGroup }
                            QQC2.RadioButton {
                                Layout.fillWidth: true
                                visible: installer.besideInfo.state === "ready"
                                enabled: installer.besideInfo.possible === true
                                QQC2.ButtonGroup.group: besideGroup
                                text: root.t("disk.beside.option")
                                checked: installer.beside
                                onClicked: installer.setBeside(true)
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: Kirigami.Units.gridUnit * 2
                                visible: installer.beside
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    text: root.t("disk.beside.size", { size: installer.sizeGib, max: installer.besideInfo.maxGib || 0 })
                                }
                                QQC2.Slider {
                                    id: sizeSlider
                                    Layout.fillWidth: true
                                    from: installer.besideInfo.minGib || 40
                                    to: Math.max(from, installer.besideInfo.maxGib || 40)
                                    stepSize: 5
                                    value: installer.sizeGib
                                    onMoved: installer.setSizeGib(Math.round(value))
                                    Accessible.name: root.t("disk.beside.size", { size: installer.sizeGib, max: installer.besideInfo.maxGib || 0 })
                                }
                            }
                            QQC2.RadioButton {
                                Layout.fillWidth: true
                                visible: installer.besideInfo.state === "ready"
                                QQC2.ButtonGroup.group: besideGroup
                                text: root.t("disk.beside.erase")
                                checked: !installer.beside
                                onClicked: installer.setBeside(false)
                            }
                            Kirigami.InlineMessage {
                                Layout.fillWidth: true
                                visible: installer.besideInfo.state === "ready" && (installer.besideInfo.problems || []).length > 0
                                type: Kirigami.MessageType.Information
                                text: (installer.besideInfo.problems || []).length > 0
                                      ? root.t("disk.beside." + installer.besideInfo.problems[0]) : ""
                            }
                        }
                        // Lemeztitkosítás (LUKS2): alapból a fiók jelszavával
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: installer.disk !== ""
                            spacing: Kirigami.Units.smallSpacing
                            QQC2.CheckBox {
                                id: encryptCheck
                                text: root.t("disk.encrypt.option")
                                checked: installer.encrypt
                                onToggled: installer.setEncrypt(checked)
                            }
                            QQC2.Label {
                                Layout.fillWidth: true
                                Layout.leftMargin: Kirigami.Units.gridUnit * 2
                                wrapMode: Text.Wrap
                                opacity: 0.75
                                text: root.t("disk.encrypt.hint")
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: Kirigami.Units.gridUnit * 2
                                visible: installer.encrypt
                                QQC2.CheckBox {
                                    text: root.t("disk.encrypt.same")
                                    checked: installer.encryptSame
                                    onToggled: installer.setEncryptSame(checked)
                                }
                                Kirigami.FormLayout {
                                    Layout.fillWidth: true
                                    visible: !installer.encryptSame
                                    Kirigami.PasswordField {
                                        id: encryptPw
                                        placeholderText: ""
                                        Kirigami.FormData.label: root.t("disk.encrypt.password")
                                        onTextEdited: installer.setEncryptPassword(encryptPw.text, encryptPw2.text)
                                    }
                                    Kirigami.PasswordField {
                                        id: encryptPw2
                                        placeholderText: ""
                                        Kirigami.FormData.label: root.t("disk.encrypt.repeat")
                                        onTextEdited: installer.setEncryptPassword(encryptPw.text, encryptPw2.text)
                                    }
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    visible: installer.encryptProblem !== ""
                                    wrapMode: Text.Wrap
                                    color: Kirigami.Theme.negativeTextColor
                                    text: installer.encryptProblem !== "" ? root.t(installer.encryptProblem) : ""
                                }
                                Kirigami.InlineMessage {
                                    Layout.fillWidth: true
                                    visible: true
                                    type: Kirigami.MessageType.Warning
                                    text: root.t("disk.encrypt.warning")
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
                        nextEnabled: installer.disk !== "" && installer.besideInfo.state !== "probing"
                                     && installer.encryptProblem === ""
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
                        source: installer.beside ? "drive-harddisk" : "dialog-warning"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: installer.beside ? root.t("confirm.beside.heading") : root.t("confirm.heading")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: installer.beside
                              ? root.t("confirm.beside.text", { size: installer.sizeGib, disk: root.diskName(installer.diskInfo) })
                              : root.t("confirm.text", { disk: root.diskName(installer.diskInfo) + " (" + (installer.diskInfo.sizeText || "") + ")" })
                    }
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        visible: installer.diskInfo.contents === "windows" && !installer.beside
                        type: Kirigami.MessageType.Warning
                        text: root.t("confirm.windows")
                    }
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        visible: installer.beside
                        type: installer.besideInfo.shrinkGib > 0 ? Kirigami.MessageType.Warning : Kirigami.MessageType.Information
                        text: installer.besideInfo.shrinkGib > 0
                              ? root.t("confirm.beside.shrink", { size: installer.besideInfo.shrinkGib })
                              : root.t("confirm.beside.free")
                    }
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        visible: installer.beside && installer.besideInfo.bitlocker === true
                        type: Kirigami.MessageType.Warning
                        text: root.t("confirm.beside.bitlocker")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: installer.beside
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: root.t("confirm.beside.menu")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: installer.encrypt
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: root.t("confirm.encrypt")
                    }
                    QQC2.CheckBox {
                        id: confirmCheck
                        Layout.alignment: Qt.AlignHCenter
                        text: installer.beside ? root.t("confirm.beside.checkbox") : root.t("confirm.checkbox")
                        FocusFrame { visible: confirmCheck.visualFocus }
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
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: installer.beside
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: root.t("done.beside")
                    }
                    QQC2.Button {
                        id: rebootButton
                        Keys.onReturnPressed: clicked()
                        Keys.onEnterPressed: clicked()
                        Layout.alignment: Qt.AlignHCenter
                        text: root.t("done.reboot")
                        icon.name: "system-reboot"
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
                        id: retryButton
                        Keys.onReturnPressed: clicked()
                        Keys.onEnterPressed: clicked()
                        Layout.alignment: Qt.AlignHCenter
                        text: root.t("error.retry")
                        icon.name: "view-refresh"
                        onClicked: installer.retry()
                    }
                }
            }
        }
    }

    // Vissza / Tovább gombsor a lépések alján. A „Tovább” nincs külön kiemelve: a kiemelés
    // összetéveszthető volt a billentyűzetfókusszal, helyette lapváltáskor ez kapja a fókuszt.
    component NavRow: RowLayout {
        id: nav
        property bool nextEnabled: true
        property alias nextButton: nextButton
        Layout.alignment: Qt.AlignHCenter
        spacing: Kirigami.Units.largeSpacing
        QQC2.Button { text: root.t("nav.back"); icon.name: "go-previous"; onClicked: installer.back() }
        QQC2.Button {
            id: nextButton
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            text: root.t("nav.next")
            icon.name: "go-next"
            enabled: nav.nextEnabled
            onClicked: installer.next()
        }
    }

    // Jól látható fókuszkeret azokhoz az elemekhez, amelyeknél a stílus alig jelzi
    component FocusFrame: Rectangle {
        anchors.fill: parent
        anchors.margins: -Kirigami.Units.smallSpacing
        radius: Kirigami.Units.cornerRadius
        color: "transparent"
        border.width: 2
        border.color: Kirigami.Theme.focusColor
    }
}
