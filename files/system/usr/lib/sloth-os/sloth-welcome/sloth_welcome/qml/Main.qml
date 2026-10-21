// Sloth OS welcome wizard: at the first sign-in, full screen.
// Steps: welcome (language) -> appearance -> apps -> installing -> done.
// The data comes from the Python side's `welcome` object, the texts from the translations
// (sloth_welcome/translations/<language>.json) through the t() function.
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
    // only bringing Windows files over (from Sloth Center): a normal window, not full screen
    visibility: welcome.windowsOnly ? Window.Windowed : Window.FullScreen
    width: Kirigami.Units.gridUnit * 60
    height: Kirigami.Units.gridUnit * 40
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    readonly property int contentWidth: Math.min(width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 52)

    // The current language's texts; on a language change every label using t() updates
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

    // While the Windows programs install (after the wizard, one by one) the window waits hidden and comes back at the end
    Connections {
        target: welcome
        function onHideRequested() { root.hide(); }
        function onShowRequested() {
            if (welcome.windowsOnly)
                root.show();
            else
                root.showFullScreen();
            root.raise();
            root.requestActivate();
        }
    }

    pageStack.initialPage: Kirigami.Page {
        padding: 0
        globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None

        StackLayout {
            anchors.fill: parent
            currentIndex: welcome.page

            // --- 0. Welcome and language ----------------------------------------
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
                    // The wizard's language; by default the system's (chosen in the installer)
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

            // --- 1. Appearance -----------------------------------------------
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
                    // The cards centred row by row, the rows evenly distributed
                    // (7 cards e.g. 4 + 3, not 6 + 1)
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
                                    // A small drawing of the layout
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
                                        // top bar (macOS)
                                        Rectangle {
                                            visible: layoutCard.modelData.id === "mac"
                                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 3 }
                                            height: 6; radius: 2; color: screen.bar
                                        }
                                        // bottom taskbar / dock
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

            // --- 2. A category (browser, office programs, …) -------------
            // Every category is a separate step; this page shows the category given by welcome.categoryIndex.
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
                            visible: categoryPage.category !== null
                                     && categoryPage.category.apps.some(a => a.source === "windows")
                            type: Kirigami.MessageType.Information
                            text: root.t("category.windows_note")
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
                                    // already installed (when the wizard runs again): ticked, not installed again
                                    readonly property bool present: welcome.presentIds.indexOf(modelData.id) !== -1
                                    readonly property bool chosen: present || welcome.selectedIds.indexOf(modelData.id) !== -1
                                    width: (root.contentWidth - Kirigami.Units.largeSpacing * 2) / 3
                                    height: Kirigami.Units.gridUnit * 4
                                    onClicked: welcome.toggle(modelData.id)
                                    Accessible.name: modelData.name
                                    // The selected card strongly highlighted: the light silver highlight color
                                    // was barely visible
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
                                            QQC2.Label { text: appCard.modelData.summary; opacity: 0.7; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: appCard.modelData.source === "windows" ? 1 : 2; elide: Text.ElideRight; font: Kirigami.Theme.smallFont }
                                            QQC2.Label {
                                                visible: appCard.present
                                                Layout.fillWidth: true
                                                elide: Text.ElideRight
                                                color: Kirigami.Theme.positiveTextColor
                                                font: Kirigami.Theme.smallFont
                                                text: root.t("app.installed")
                                            }
                                            // Windows program: it is installed after the wizard
                                            QQC2.Label {
                                                visible: appCard.modelData.source === "windows" && !appCard.present
                                                Layout.fillWidth: true
                                                wrapMode: Text.Wrap
                                                maximumLineCount: 2
                                                elide: Text.ElideRight
                                                color: Kirigami.Theme.linkColor
                                                font: Kirigami.Theme.smallFont
                                                text: root.t("app.windows_badge")
                                            }
                                        }
                                        // A real checkbox. (Breeze has no "checkbox-unchecked" icon,
                                        // the ticked "checkbox" showed instead.) It does not toggle its own
                                        // state, it only passes the click on; the tick comes from the selection.
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

                // Bottom bar: step indicator, back, next / install
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
                                // After the browser step we say so if none was chosen
                                if (welcome.categoryIndex === 0 && welcome.selectedInCategory.length === 0)
                                    noBrowser.open();
                                else
                                    welcome.next();
                            }
                        }
                    }
                }
            }

            // --- 3. Installing ------------------------------------------------
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

            // --- 4. Done -------------------------------------------------------
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
                    // Downloaded Windows installers: these come first (one by one), the restart only after them
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        visible: welcome.pendingWindows
                        type: Kirigami.MessageType.Information
                        text: root.t("done.windows_hint", { names: welcome.pendingWindowsNames.join(", ") })
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignHCenter
                        visible: welcome.pendingWindows
                        highlighted: true
                        icon.name: "go-next"
                        text: root.t("done.windows_continue")
                        onClicked: welcome.runWindowsQueue()
                    }
                    // After installing, restarting is the main button: then every new app loads properly
                    QQC2.Label {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        visible: welcome.anyInstalled && !welcome.pendingWindows && !welcome.windowsQueueDone
                        text: root.t("done.restart_hint")
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        visible: !welcome.pendingWindows
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Button {
                            text: root.t("done.start")
                            icon.name: "go-next"
                            highlighted: !welcome.anyInstalled
                            onClicked: welcome.finish(false)
                        }
                        QQC2.Button {
                            visible: welcome.anyInstalled
                            text: root.t("done.restart")
                            icon.name: "system-reboot"
                            highlighted: true
                            onClicked: welcome.finish(true)
                        }
                    }
                    // Support (Ko-fi): quietly, below the main buttons; the address is in the text too, in case there is no browser
                    QQC2.Label {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.6
                        font: Kirigami.Theme.smallFont
                        text: root.t("done.support")
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignHCenter
                        flat: true
                        icon.name: "emblem-favorite"
                        text: root.t("done.support_button")
                        onClicked: Qt.openUrlExternally("https://ko-fi.com/slothos")
                    }
                }
            }

            // --- 5. Passwords (after the appearance) ---------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 32)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignHCenter
                        source: "security-medium"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("security.heading")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: root.t("security.text")
                    }
                    QQC2.ButtonGroup { id: securityGroup }
                    QQC2.RadioButton {
                        Layout.fillWidth: true
                        enabled: welcome.isAdmin
                        QQC2.ButtonGroup.group: securityGroup
                        text: root.t("security.all")
                        checked: welcome.securityChoice === "all"
                        onClicked: welcome.setSecurityChoice("all")
                    }
                    QQC2.RadioButton {
                        Layout.fillWidth: true
                        enabled: welcome.isAdmin
                        QQC2.ButtonGroup.group: securityGroup
                        text: root.t("security.recommended")
                        checked: welcome.securityChoice === "recommended"
                        onClicked: welcome.setSecurityChoice("recommended")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: !welcome.isAdmin
                        wrapMode: Text.Wrap
                        color: Kirigami.Theme.neutralTextColor
                        text: root.t("security.not_admin")
                    }
                    QQC2.CheckBox {
                        Layout.fillWidth: true
                        text: root.t("security.autologin")
                        checked: welcome.autologin
                        onToggled: welcome.setAutologin(checked)
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        font: Kirigami.Theme.smallFont
                        text: root.t("security.later")
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

            // --- 6. Sharing experiences (after the passwords) -------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 32)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignHCenter
                        source: "network-workgroup"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("sharing.heading")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: root.t("sharing.text")
                    }
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        visible: true
                        type: Kirigami.MessageType.Information
                        text: root.t("sharing.what")
                    }
                    QQC2.ButtonGroup { id: sharingGroup }
                    QQC2.RadioButton {
                        Layout.fillWidth: true
                        QQC2.ButtonGroup.group: sharingGroup
                        text: root.t("sharing.yes")
                        checked: welcome.sharingChoice === "yes"
                        onClicked: welcome.setSharingChoice("yes")
                    }
                    QQC2.RadioButton {
                        Layout.fillWidth: true
                        QQC2.ButtonGroup.group: sharingGroup
                        text: root.t("sharing.no")
                        checked: welcome.sharingChoice === "no"
                        onClicked: welcome.setSharingChoice("no")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        font: Kirigami.Theme.smallFont
                        text: root.t("sharing.later")
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Button { text: root.t("nav.back"); icon.name: "go-previous"; onClicked: welcome.back() }
                        QQC2.Button {
                            text: root.t("nav.next")
                            icon.name: "go-next"
                            highlighted: true
                            enabled: welcome.sharingChoice !== ""
                            onClicked: welcome.next()
                        }
                    }
                }
            }

            // --- 7. Bringing files over from Windows (only if there is a Windows partition) ----------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 32)
                    spacing: Kirigami.Units.largeSpacing * 2
                    readonly property string winState: welcome.windowsState
                    readonly property bool busy: winState === "scanning" || winState === "copying"
                    Kirigami.Icon {
                        Layout.alignment: Qt.AlignHCenter
                        source: "folder-download"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.t("windows.heading")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: root.t("windows.text")
                    }
                    // survey
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        visible: parent.winState === "scanning" || parent.winState === "idle"
                        QQC2.BusyIndicator { running: parent.visible }
                        QQC2.Label { text: root.t("windows.scanning") }
                    }
                    // choice
                    RowLayout {
                        Layout.fillWidth: true
                        visible: parent.winState === "ready" && welcome.windowsUsers.length > 1
                        QQC2.Label { text: root.t("windows.user") }
                        QQC2.ComboBox {
                            Layout.fillWidth: true
                            model: welcome.windowsUsers
                            currentIndex: Math.max(0, welcome.windowsUsers.indexOf(welcome.windowsUser))
                            onActivated: index => welcome.setWindowsUser(welcome.windowsUsers[index])
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: parent.winState === "ready"
                        Repeater {
                            model: welcome.windowsFolders
                            delegate: QQC2.CheckBox {
                                required property var modelData
                                Layout.fillWidth: true
                                text: root.t("windows.folder." + modelData.key) + " (" + modelData.size + ")"
                                checked: modelData.selected
                                onToggled: welcome.toggleWindowsFolder(modelData.key)
                            }
                        }
                        QQC2.CheckBox {
                            Layout.fillWidth: true
                            visible: welcome.windowsBookmarkCount > 0
                            text: root.t("windows.bookmarks")
                            checked: welcome.windowsBookmarks
                            onToggled: welcome.setWindowsBookmarks(checked)
                        }
                    }
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        visible: parent.winState === "ready"
                        type: Kirigami.MessageType.Information
                        text: root.t("windows.onedrive")
                    }
                    // copying
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: parent.winState === "copying"
                        QQC2.Label { Layout.fillWidth: true; text: root.t("windows.copying") }
                        QQC2.ProgressBar {
                            Layout.fillWidth: true
                            from: 0; to: 100
                            value: Math.max(0, welcome.windowsProgress)
                            indeterminate: welcome.windowsProgress < 0
                        }
                        QQC2.Label { opacity: 0.7; text: welcome.windowsDetail }
                    }
                    // result, errors
                    Kirigami.InlineMessage {
                        Layout.fillWidth: true
                        visible: ["done", "nospace", "locked", "none", "failed"].indexOf(parent.winState) >= 0
                        type: parent.winState === "done" ? Kirigami.MessageType.Positive
                              : parent.winState === "none" ? Kirigami.MessageType.Information
                              : Kirigami.MessageType.Warning
                        text: parent.winState === "done" || parent.winState === "nospace" ? welcome.windowsDetail
                              : root.t("windows." + parent.winState)
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Button {
                            visible: !welcome.windowsOnly
                            enabled: !parent.parent.busy
                            text: root.t("nav.back"); icon.name: "go-previous"; onClicked: welcome.back()
                        }
                        QQC2.Button {
                            visible: parent.parent.winState === "nospace"
                            text: root.t("windows.change"); icon.name: "edit-undo"; onClicked: welcome.retryWindows()
                        }
                        QQC2.Button {
                            visible: parent.parent.winState === "ready"
                            enabled: welcome.windowsFolders.some(f => f.selected)
                                     || (welcome.windowsBookmarks && welcome.windowsBookmarkCount > 0)
                            highlighted: true
                            icon.name: "folder-download"
                            text: root.t("windows.copy")
                            onClicked: welcome.startWindowsCopy()
                        }
                        QQC2.Button {
                            enabled: !parent.parent.busy
                            highlighted: parent.parent.winState !== "ready"
                            icon.name: "go-next"
                            text: welcome.windowsOnly ? root.t("nav.finish")
                                  : parent.parent.winState === "ready" || parent.parent.winState === "nospace"
                                    ? root.t("nav.skip") : root.t("nav.next")
                            onClicked: welcome.next()
                        }
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
