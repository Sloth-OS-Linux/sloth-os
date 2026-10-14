// Sloth OS üdvözlő varázsló: első bejelentkezéskor, teljes képernyőn.
// Lépések: üdvözlés (nyelv) -> megjelenés -> appok -> telepítés -> kész.
// Az adatok a Python oldali `welcome` objektumból jönnek, a szövegek a fordításokból
// (sloth_welcome/translations/<nyelv>.json) a t() függvényen keresztül.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: t("window.title")
    visible: true
    visibility: Window.FullScreen
    width: Kirigami.Units.gridUnit * 60
    height: Kirigami.Units.gridUnit * 40
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    readonly property int contentWidth: Math.min(width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 52)

    // Az aktuális nyelv szövegei; nyelvváltáskor minden t()-t használó felirat frissül
    readonly property var strings: welcome.strings
    function t(key, args) {
        let text = root.strings[key];
        if (text === undefined)
            return key;
        if (args)
            for (const k in args)
                text = text.split("{" + k + "}").join(args[k]);
        return text;
    }

    pageStack.initialPage: Kirigami.Page {
        padding: 0
        globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None

        StackLayout {
            anchors.fill: parent
            currentIndex: welcome.page

            // --- 0. Üdvözlés és nyelv ----------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: root.contentWidth
                    spacing: Kirigami.Units.largeSpacing * 2
                    Image {
                        Layout.alignment: Qt.AlignHCenter
                        source: "file:///usr/share/sloth-os/logo/sloth-logo.svg"
                        sourceSize.width: Kirigami.Units.gridUnit * 10
                        sourceSize.height: Kirigami.Units.gridUnit * 10
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
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
                    // A varázsló nyelve; alapból a rendszeré (amit a telepítőben választott)
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
                            implicitWidth: Kirigami.Units.gridUnit * 12
                            model: welcome.languages
                            textRole: "name"
                            valueRole: "code"
                            currentIndex: count > 0 ? indexOfValue(welcome.language) : -1
                            onActivated: welcome.setLanguage(currentValue)
                        }
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        text: root.t("welcome.start")
                        icon.name: "go-next"
                        highlighted: true
                        onClicked: welcome.next()
                    }
                }
            }

            // --- 1. Megjelenés -----------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: root.contentWidth
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: root.t("look.colors")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: root.t("look.colors_hint")
                    }
                    // A kártyák soronként középre igazítva, a sorok egyenletesen elosztva
                    // (7 kártya pl. 4 + 3, nem 6 + 1)
                    Column {
                        id: schemeGrid
                        readonly property int cardWidth: Kirigami.Units.gridUnit * 9
                        readonly property var rows: {
                            const all = welcome.schemes;
                            const fit = Math.max(1, Math.floor((root.contentWidth + spacing) / (cardWidth + spacing)));
                            const per = Math.ceil(all.length / Math.ceil(all.length / fit));
                            const out = [];
                            for (let i = 0; i < all.length; i += per)
                                out.push(all.slice(i, i + per));
                            return out;
                        }
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.largeSpacing
                        Repeater {
                            model: schemeGrid.rows
                            delegate: Row {
                                id: schemeRow
                                required property var modelData
                                anchors.horizontalCenter: parent ? parent.horizontalCenter : undefined
                                spacing: Kirigami.Units.largeSpacing
                                Repeater {
                                    model: schemeRow.modelData
                                    delegate: QQC2.AbstractButton {
                                        id: schemeCard
                                        required property var modelData
                                        readonly property bool current: welcome.currentScheme === modelData.id
                                        width: schemeGrid.cardWidth
                                        height: Kirigami.Units.gridUnit * 7
                                        onClicked: welcome.setScheme(modelData.id)
                                        Accessible.name: modelData.name
                                        contentItem: ColumnLayout {
                                            spacing: Kirigami.Units.smallSpacing
                                            Rectangle {
                                                Layout.fillWidth: true
                                                Layout.fillHeight: true
                                                radius: Kirigami.Units.cornerRadius
                                                color: schemeCard.modelData.colors[0]
                                                border.width: schemeCard.current ? 3 : 1
                                                border.color: schemeCard.current ? Kirigami.Theme.highlightColor
                                                                                 : Qt.rgba(0.5, 0.5, 0.5, 0.4)
                                                Rectangle {
                                                    anchors.left: parent.left
                                                    anchors.right: parent.right
                                                    anchors.bottom: parent.bottom
                                                    anchors.margins: Kirigami.Units.largeSpacing
                                                    height: Kirigami.Units.gridUnit
                                                    radius: height / 3
                                                    color: schemeCard.modelData.colors[1]
                                                }
                                                Rectangle {
                                                    x: Kirigami.Units.largeSpacing
                                                    y: Kirigami.Units.largeSpacing
                                                    width: parent.width * 0.5
                                                    height: Kirigami.Units.smallSpacing * 2
                                                    radius: height / 2
                                                    color: schemeCard.modelData.colors[2]
                                                }
                                            }
                                            QQC2.Label {
                                                Layout.fillWidth: true
                                                horizontalAlignment: Text.AlignHCenter
                                                elide: Text.ElideRight
                                                text: schemeCard.modelData.name
                                                font.bold: schemeCard.current
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.largeSpacing * 2
                        horizontalAlignment: Text.AlignHCenter
                        level: 3
                        text: root.t("look.taskbar")
                    }
                    Flow {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: (Kirigami.Units.gridUnit * 12 + Kirigami.Units.largeSpacing) * 3
                        spacing: Kirigami.Units.largeSpacing
                        Repeater {
                            model: welcome.layouts
                            delegate: QQC2.AbstractButton {
                                id: layoutCard
                                required property var modelData
                                readonly property bool current: welcome.currentLayout === modelData.id
                                width: Kirigami.Units.gridUnit * 12
                                height: Kirigami.Units.gridUnit * 9
                                onClicked: welcome.setLayout(modelData.id)
                                Accessible.name: modelData.name
                                contentItem: ColumnLayout {
                                    spacing: Kirigami.Units.smallSpacing
                                    // Kis rajz az elrendezésről
                                    Rectangle {
                                        id: screen
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: Kirigami.Units.cornerRadius
                                        color: Qt.alpha(Kirigami.Theme.textColor, 0.08)
                                        border.width: layoutCard.current ? 3 : 1
                                        border.color: layoutCard.current ? Kirigami.Theme.highlightColor : Qt.rgba(0.5, 0.5, 0.5, 0.4)
                                        readonly property color bar: Qt.alpha(Kirigami.Theme.textColor, 0.35)
                                        readonly property color dot: Kirigami.Theme.highlightColor
                                        // felső sáv (macOS)
                                        Rectangle {
                                            visible: layoutCard.modelData.id === "mac"
                                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 3 }
                                            height: 6; radius: 2; color: screen.bar
                                        }
                                        // alsó tálca / dokk
                                        Rectangle {
                                            id: taskbar
                                            anchors.bottom: parent.bottom
                                            anchors.bottomMargin: layoutCard.modelData.id === "mac" ? 8 : 3
                                            x: layoutCard.modelData.id === "mac" ? parent.width * 0.3 : 3
                                            width: layoutCard.modelData.id === "mac" ? parent.width * 0.4 : parent.width - 6
                                            height: 12; radius: layoutCard.modelData.id === "mac" ? 5 : 2
                                            color: screen.bar
                                            Row {
                                                anchors.verticalCenter: parent.verticalCenter
                                                x: layoutCard.modelData.id === "windows10" ? 4 : (parent.width - width) / 2
                                                spacing: 3
                                                Repeater {
                                                    model: 4
                                                    Rectangle {
                                                        required property int index
                                                        width: 7; height: 7; radius: 2
                                                        color: index === 0 && layoutCard.modelData.id !== "mac" ? screen.dot : Qt.alpha(Kirigami.Theme.backgroundColor, 0.9)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        horizontalAlignment: Text.AlignHCenter
                                        elide: Text.ElideRight
                                        text: layoutCard.modelData.name
                                        font.bold: layoutCard.current
                                    }
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        horizontalAlignment: Text.AlignHCenter
                                        elide: Text.ElideRight
                                        opacity: 0.7
                                        font: Kirigami.Theme.smallFont
                                        text: layoutCard.modelData.description
                                    }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Button { text: root.t("nav.back"); icon.name: "go-previous"; onClicked: welcome.back() }
                        QQC2.Button { text: root.t("nav.next"); icon.name: "go-next"; highlighted: true; onClicked: welcome.next() }
                    }
                }
            }

            // --- 2. Egy kategória (böngésző, irodai programok, …) -------------
            // Minden kategória külön lépés; ez a lap a welcome.categoryIndex szerinti kategóriát mutatja.
            ColumnLayout {
                id: categoryPage
                readonly property var category: welcome.categoryIndex >= 0 ? welcome.categories[welcome.categoryIndex] : null
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
                            source: categoryPage.category ? categoryPage.category.icon : ""
                            fallback: categoryPage.category && categoryPage.category.fallback_icon
                                      ? categoryPage.category.fallback_icon : "unknown"
                            implicitWidth: Kirigami.Units.iconSizes.huge
                            implicitHeight: Kirigami.Units.iconSizes.huge
                        }
                        Kirigami.Heading {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            text: categoryPage.category ? categoryPage.category.name : ""
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: categoryPage.category ? categoryPage.category.hint + " " + root.t("category.multiple") : ""
                        }
                        Kirigami.InlineMessage {
                            Layout.fillWidth: true
                            visible: !welcome.online
                            type: Kirigami.MessageType.Warning
                            text: root.t("offline.text")
                            actions: [
                                Kirigami.Action {
                                    text: root.t("offline.settings")
                                    icon.name: "network-wireless"
                                    onTriggered: welcome.openNetworkSettings()
                                },
                                Kirigami.Action {
                                    text: root.t("offline.retry")
                                    icon.name: "view-refresh"
                                    onTriggered: welcome.recheckOnline()
                                }
                            ]
                        }

                        Flow {
                            Layout.fillWidth: true
                            Layout.topMargin: Kirigami.Units.largeSpacing
                            spacing: Kirigami.Units.largeSpacing
                            Repeater {
                                model: categoryPage.category ? categoryPage.category.apps : []
                                delegate: QQC2.AbstractButton {
                                    id: appCard
                                    required property var modelData
                                    readonly property bool chosen: welcome.selectedIds.indexOf(modelData.id) !== -1
                                    width: (root.contentWidth - Kirigami.Units.largeSpacing * 2) / 3
                                    height: Kirigami.Units.gridUnit * 4
                                    onClicked: welcome.toggle(modelData.id)
                                    Accessible.name: modelData.name
                                    // A kijelölt kártya erősen kiemelve: a világos ezüst kiemelőszín
                                    // halványan alig látszott
                                    background: Rectangle {
                                        radius: Kirigami.Units.cornerRadius
                                        color: appCard.chosen ? Qt.alpha(Kirigami.Theme.highlightColor, appCard.hovered ? 0.45 : 0.35)
                                             : appCard.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.08)
                                             : Qt.alpha(Kirigami.Theme.textColor, 0.03)
                                        border.width: appCard.chosen ? 3 : 1
                                        border.color: appCard.chosen ? Kirigami.Theme.highlightColor
                                                                     : Qt.alpha(Kirigami.Theme.textColor, 0.15)
                                    }
                                    contentItem: RowLayout {
                                        spacing: Kirigami.Units.largeSpacing
                                        Image {
                                            Layout.leftMargin: Kirigami.Units.largeSpacing
                                            source: appCard.modelData.iconUrl
                                            sourceSize.width: Kirigami.Units.iconSizes.large
                                            sourceSize.height: Kirigami.Units.iconSizes.large
                                            Layout.preferredWidth: Kirigami.Units.iconSizes.large
                                            Layout.preferredHeight: Kirigami.Units.iconSizes.large
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 0
                                            QQC2.Label { text: appCard.modelData.name; font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight }
                                            QQC2.Label { text: appCard.modelData.summary; opacity: 0.7; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; font: Kirigami.Theme.smallFont }
                                        }
                                        // Valódi jelölőnégyzet. (A Breeze-ben nincs "checkbox-unchecked" ikon,
                                        // helyette a bepipált "checkbox" látszott.) A saját állapotát nem
                                        // váltja, csak továbbadja a kattintást; a pipát a kiválasztás adja.
                                        QQC2.CheckBox {
                                            Layout.rightMargin: Kirigami.Units.largeSpacing
                                            checkState: appCard.chosen ? Qt.Checked : Qt.Unchecked
                                            nextCheckState: function () { return checkState; }
                                            onClicked: welcome.toggle(appCard.modelData.id)
                                            Accessible.name: appCard.modelData.name
                                        }
                                    }
                                }
                            }
                        }
                        Item { implicitHeight: Kirigami.Units.gridUnit }
                    }
                }

                // Alsó sáv: lépésjelző, vissza, tovább / telepítés
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: bar.implicitHeight + Kirigami.Units.largeSpacing * 2
                    color: Kirigami.Theme.alternateBackgroundColor
                    RowLayout {
                        id: bar
                        anchors.centerIn: parent
                        width: root.contentWidth
                        QQC2.Label {
                            Layout.fillWidth: true
                            opacity: 0.7
                            elide: Text.ElideRight
                            text: root.t("step.counter", { n: welcome.stepNumber, total: welcome.stepCount }) +
                                  (welcome.selectedIds.length === 0 ? ""
                                   : "  ·  " + root.t(welcome.selectedIds.length === 1 ? "step.selected_one" : "step.selected_many",
                                                      { count: welcome.selectedIds.length }))
                        }
                        QQC2.Button { text: root.t("nav.back"); icon.name: "go-previous"; onClicked: welcome.back() }
                        QQC2.Button {
                            highlighted: true
                            enabled: !welcome.lastCategory || welcome.selectedIds.length === 0 || welcome.online
                            text: !welcome.lastCategory ? root.t(welcome.selectedInCategory.length === 0 ? "nav.skip" : "nav.next")
                                  : root.t(welcome.selectedIds.length === 0 ? "nav.finish" : "nav.install")
                            icon.name: welcome.lastCategory && welcome.selectedIds.length > 0 ? "download" : "go-next"
                            onClicked: {
                                // A böngészős lépés után szólunk, ha nem választott egyet sem
                                if (welcome.categoryIndex === 0 && welcome.selectedInCategory.length === 0)
                                    noBrowser.open();
                                else
                                    welcome.next();
                            }
                        }
                    }
                }
            }

            // --- 3. Telepítés ------------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 30)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Image {
                        Layout.alignment: Qt.AlignHCenter
                        source: "file:///usr/share/sloth-os/logo/sloth-logo.svg"
                        sourceSize.width: Kirigami.Units.gridUnit * 6
                        sourceSize.height: Kirigami.Units.gridUnit * 6
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        level: 2
                        text: welcome.statusText
                    }
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: Math.max(0, welcome.progress)
                        indeterminate: welcome.progress < 0
                    }
                    QQC2.Label {
                        Layout.alignment: Qt.AlignHCenter
                        opacity: 0.7
                        text: welcome.detailText
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.smallSpacing
                        Repeater {
                            model: welcome.selectedIds
                            delegate: RowLayout {
                                id: row
                                required property string modelData
                                readonly property string state: welcome.appStates[modelData] || "waiting"
                                Layout.fillWidth: true
                                spacing: Kirigami.Units.largeSpacing
                                Image {
                                    source: "file:///usr/share/sloth-os/welcome/icons/" + row.modelData + ".png"
                                    sourceSize.width: Kirigami.Units.iconSizes.smallMedium
                                    sourceSize.height: Kirigami.Units.iconSizes.smallMedium
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    text: {
                                        for (const c of welcome.categories)
                                            for (const a of c.apps)
                                                if (a.id === row.modelData) return a.name;
                                        return row.modelData;
                                    }
                                }
                                QQC2.BusyIndicator {
                                    visible: row.state === "installing"
                                    running: visible
                                    implicitWidth: Kirigami.Units.iconSizes.smallMedium
                                    implicitHeight: Kirigami.Units.iconSizes.smallMedium
                                }
                                Kirigami.Icon {
                                    visible: row.state !== "installing"
                                    implicitWidth: Kirigami.Units.iconSizes.smallMedium
                                    implicitHeight: Kirigami.Units.iconSizes.smallMedium
                                    source: row.state === "done" ? "checkmark"
                                          : row.state === "failed" ? "dialog-error" : "content-loading-symbolic"
                                    opacity: row.state === "waiting" ? 0.4 : 1
                                }
                            }
                        }
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

            // --- 4. Kész -------------------------------------------------------
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
                        level: 2
                        text: welcome.summaryText
                    }
                    Repeater {
                        model: welcome.failures
                        delegate: QQC2.Label {
                            required property var modelData
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            text: "• " + modelData.name + ": " + modelData.error
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        visible: welcome.failures.length > 0
                        text: root.t("done.retry_hint")
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        horizontalAlignment: Text.AlignHCenter
                        level: 4
                        text: root.t("done.extras")
                    }
                    Flow {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: implicitWidth
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Button {
                            visible: welcome.steamInstalled
                            icon.source: "file:///usr/share/sloth-os/welcome/icons/com.valvesoftware.Steam.png"
                            text: root.t("done.steam")
                            onClicked: welcome.quickAction("steam")
                        }
                        QQC2.Button {
                            icon.name: "applications-internet"
                            text: root.t("done.accounts")
                            onClicked: welcome.quickAction("accounts")
                        }
                        QQC2.Button {
                            icon.name: "preferences-desktop-locale"
                            text: root.t("done.language")
                            onClicked: welcome.quickAction("language")
                        }
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignHCenter
                        text: root.t("done.start")
                        icon.name: "go-next"
                        highlighted: true
                        onClicked: welcome.finish()
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: noBrowser
        title: root.t("nobrowser.title")
        subtitle: root.t("nobrowser.text")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: root.t("nobrowser.choose")
                icon.name: "go-previous"
                onTriggered: noBrowser.close()
            },
            Kirigami.Action {
                text: root.t("nobrowser.ok")
                icon.name: "go-next"
                onTriggered: { noBrowser.close(); welcome.next(); }
            }
        ]
    }
}
