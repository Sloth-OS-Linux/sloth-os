// Sloth Center – main window: the modules on the left, the selected page on the right.
pragma ComponentBehavior: Bound
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: L.t("Sloth Center")
    visible: true
    width: Kirigami.Units.gridUnit * 56
    height: Kirigami.Units.gridUnit * 38
    minimumWidth: Kirigami.Units.gridUnit * 30
    minimumHeight: Kirigami.Units.gridUnit * 24

    // The list of modules. Modules with "ready: false" are still being made (ROADMAP phase 3). "more: true": not in
    // the list on the left (that is for everyday settings) but under More settings, with every KDE page.
    // The sidebar in groups ("section"): first what people use every day, then the rest by topic; "more: true" ones
    // are only in More settings. "kcm": a KDE settings page inside Sloth Center.
    readonly property var modules: [
        { id: "network", name: L.t("Wi-Fi and network"), icon: "network-wireless", page: "WifiPage.qml", ready: true, section: "daily" },
        { id: "bluetoothpage", name: L.t("Bluetooth"), icon: "preferences-system-bluetooth", kcm: "kcm_bluetooth", ready: true, section: "daily" },
        { id: "displaypage", name: L.t("Display"), icon: "preferences-desktop-display", kcm: "kcm_kscreen", ready: true, section: "daily" },
        { id: "soundpage", name: L.t("Sound"), icon: "preferences-desktop-sound", kcm: "kcm_pulseaudio", ready: true, section: "daily" },
        { id: "power", name: L.t("Power and battery"), icon: "preferences-system-power-management", page: "PowerPage.qml", ready: true, section: "daily" },
        { id: "appearance", name: L.t("Appearance"), icon: "preferences-desktop-theme-global", page: "AppearancePage.qml", ready: true, section: "daily" },
        { id: "updates", name: L.t("Updates"), icon: "system-software-update", page: "UpdatesPage.qml", ready: true, section: "daily" },
        { id: "apps", name: L.t("Apps"), icon: "applications-all", page: "AppsPage.qml", ready: true, section: "apps" },
        { id: "winprograms", name: L.t("Windows programs"), icon: "application-x-ms-dos-executable", page: "WinProgramsPage.qml", ready: true, section: "apps" },
        { id: "games", name: L.t("Games"), icon: "input-gamepad", page: "GamesPage.qml", ready: true, section: "apps" },
        { id: "accounts", name: L.t("Account and security"), icon: "preferences-system-users", page: "AccountsPage.qml", ready: true, section: "people" },
        { id: "parental", name: L.t("Parental controls"), icon: "user-group-properties", page: "ParentalPage.qml", ready: true, section: "people" },
        { id: "accessibility", name: L.t("Accessibility"), icon: "preferences-desktop-accessibility", page: "AccessibilityPage.qml", ready: true, section: "people" },
        { id: "status", name: L.t("System status"), icon: "dialog-information", page: "SystemStatusPage.qml", ready: true, section: "system" },
        { id: "printers", name: L.t("Printers and scanners"), icon: "printer", page: "PrintersPage.qml", ready: true, section: "system" },
        { id: "drivers", name: L.t("Drivers and hardware"), icon: "preferences-devices-cpu", page: "DriversPage.qml", ready: true, section: "system" },
        { id: "disks", name: L.t("Disks"), icon: "drive-harddisk", page: "DisksPage.qml", ready: true, section: "system" },
        { id: "backup", name: L.t("File backup"), icon: "backup", page: "BackupPage.qml", ready: true, section: "system" },
        { id: "reset", name: L.t("Reset this PC"), icon: "edit-undo", page: "ResetPage.qml", ready: true, section: "system" },
        { id: "help", name: L.t("Help and feedback"), icon: "help-contents", page: "HelpPage.qml", ready: true, section: "help" },
        // reached from Help and feedback (and the search): not a row of its own, that row stays lit
        { id: "feedback", name: L.t("Feedback"), icon: "mail-message-new", page: "FeedbackPage.qml", ready: true, under: "help", section: "help" },
        { id: "kde", name: L.t("More settings"), icon: "preferences-system", page: "KdeSettingsPage.qml", ready: true, section: "all" },
        { id: "services", name: L.t("Services"), icon: "preferences-system-services", page: "ServicesPage.qml", ready: true, more: true, section: "zmore" },
        { id: "usbguide", name: L.t("Create installation media"), icon: "drive-removable-media-usb", page: "UsbGuidePage.qml", ready: true, more: true, section: "zmore" },
        { id: "containers", name: L.t("Developer environments"), icon: "utilities-terminal", page: "ContainersPage.qml", ready: true, more: true, section: "zmore" },
        { id: "advanced", name: L.t("Advanced settings"), icon: "configure", page: "AdvancedPage.qml", ready: true, more: true, section: "zmore" },
        { id: "devpanel", name: L.t("Developer panel"), icon: "applications-development", page: "DevPanelPage.qml", ready: true, more: true, section: "zmore" }
    ]
    readonly property var sectionNames: ({
        daily: "", apps: L.t("Apps and games"), people: L.t("Accounts and family"), system: L.t("System"),
        help: "", all: "", zmore: ""
    })
    property int currentIndex: 0      // the row lit up in the list on the left
    property int shownIndex: 0        // the module shown now (a "more" one too); a KDE page's Back returns here
    property int guideStep: 0

    // The user's choice about the window: the list on the left narrowed to icons
    readonly property alias ui: uiSettings
    Settings {
        id: uiSettings
        category: "view"
        property bool sidebarCollapsed: false
    }

    // More settings: the sidebar turns into its list (Back at the top returns to the everyday list), the same rows
    // and group titles: every KDE settings page in KDE's own topics (kde_settings.py) and Sloth OS's advanced pages
    // ("more: true"). A row opens its page on the right like any other. KDE pages that a Sloth Center page covers
    // ("covered") show only in the search.
    property bool moreMode: false
    property string moreSelected: ""  // the lit row of that list (a page's id)
    // The search at the top of the sidebar (both lists): Sloth Center's pages by their name and every text on them
    // (search.py), then KDE's pages by their names, descriptions and keywords, under their topics
    property string filter: ""
    readonly property string needle: searchIndex.normalize(filter)
    readonly property bool searching: needle !== ""
    property string searchSelected: ""  // the lit row of the results
    Loader {
        id: catalogLoader
        source: "KcmCatalogView.qml"
        // loaded the first time it is needed, then kept
        active: root.moreMode || root.searching || status === Loader.Ready
        visible: false
    }
    readonly property var kdeGroups: catalogLoader.status === Loader.Ready && catalogLoader.item.modules.length
                                     ? kde.groups(catalogLoader.item.modules) : []
    // a KDE page's words for the search (normalized once, not at every key press)
    readonly property var kdeTexts: {
        const out = {};
        for (const g of kdeGroups)
            for (const p of g.pages)
                out[p.id] = [p.name, p.description, p.id].concat(p.keywords || [])
                            .map(t => searchIndex.normalize(t)).join("\n");
        return out;
    }
    function kdeMatches(p, n) {
        return (kdeTexts[p.id] || "").includes(n);
    }
    readonly property var moreEntries: {
        const out = [];
        for (const g of kdeGroups)
            for (const p of g.pages)
                if (!p.covered)
                    out.push(Object.assign({}, p, { section: g.name || L.t("Other") }));
        for (const m of modules.filter(m => m.more))
            out.push({ id: m.id, name: m.name, icon: m.icon, description: "", sloth: true, section: "Sloth OS" });
        return out;
    }
    // the texts of Sloth Center's pages, once (search.py); a KDE page of the sidebar (Bluetooth…) by KDE's own words
    readonly property var pageTexts: {
        const out = {};
        for (const m of modules)
            if (m.page && m.id !== "kde")  // More settings' introduction lists KDE's topics: found by their own pages
                out[m.id] = searchIndex.pageText(m.page);
        return out;
    }
    readonly property var searchResults: {
        if (!searching)
            return [];
        const n = needle;
        const ours = [], byText = [];
        const kdeById = {};
        for (const g of kdeGroups)
            for (const p of g.pages)
                kdeById[p.id] = p;
        for (const m of modules) {
            const e = { id: m.id, name: m.name, icon: m.icon, description: "", sloth: true, section: L.t("Sloth Center") };
            if (searchIndex.normalize(m.name).includes(n))
                ours.push(e);  // a match in the name first
            else if ((pageTexts[m.id] || "").includes(n) || (m.kcm && kdeById[m.kcm] && kdeMatches(kdeById[m.kcm], n)))
                byText.push(e);
        }
        const out = ours.concat(byText);
        // not twice: a KDE page that is a row of the sidebar (Bluetooth…), or that a page of ours of the same name covers
        const rows = new Set(modules.filter(m => m.kcm).map(m => m.kcm));
        const names = new Set(modules.map(m => searchIndex.normalize(m.name)));
        for (const g of kdeGroups)
            for (const p of g.pages)
                if (!rows.has(p.id) && !(p.covered && names.has(searchIndex.normalize(p.name))) && kdeMatches(p, n))
                    out.push(Object.assign({}, p, { section: g.name || L.t("Other") }));
        return out;
    }
    function openEntry(p) {
        if (searching)
            searchSelected = p.id;
        if (p.sloth)
            openModuleById(p.id);
        else if (p.widget)
            kde.openWindow(p.id);  // an older KDE page: its own window, the row on the left stays as it was
        else
            openKcm(p.id, "", p.name, true);
    }
    function focusSearch() {
        uiSettings.sidebarCollapsed = false;
        Qt.callLater(() => searchField.forceActiveFocus());
    }
    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: root.focusSearch()
    }

    function leaveMore() {
        moreMode = false;
        searchField.text = "";
        Qt.callLater(() => moduleList.positionViewAtBeginning());  // the everyday rows first, as at the start
    }

    // The first-run guide: each step lights up its pages in the list on the left, the rest of the window goes dark
    readonly property var guideSteps: [
        { modules: ["updates"], title: L.t("Keep Sloth OS up to date"),
          text: L.t("The Updates page installs system updates and lets you return to the previous version if an update causes trouble.") },
        { modules: ["apps", "winprograms", "games"], title: L.t("Find and manage programs"),
          text: L.t("Programs is where you install and start Windows programs. Games has settings for Steam and other game tools.") },
        { modules: ["appearance"], title: L.t("Change how it looks"),
          text: L.t("Appearance switches the taskbar layout and the colors, the same ones as in the welcome wizard. You can change them any time.") },
        { modules: ["help", "backup", "disks"], title: L.t("Back up files and get help"),
          text: L.t("File backup shows saved copies of your files. Feedback is the place to ask for help, and Disks can help bring files over from Windows.") }
    ]

    function openGuide() {
        if (moreMode || searching)
            leaveMore();
        guideStep = 0;
        guideDialog.open();
        Qt.callLater(guideDialog.place);
    }

    // A KDE page with changes not applied yet (KcmPage.qml): ask first, as KDE's System Settings does
    property var pendingLeave: null
    function leaveKdePage(then) {
        const current = pageStack.items.length ? pageStack.items[0] : null;
        if (current && current.view && current.view.needsSave) {
            pendingLeave = then;
            unsavedDialog.open();
            return;
        }
        then();
    }

    function openModule(index) {
        leaveKdePage(() => showModule(index));
    }

    // A KDE settings page inside Sloth Center (kde_settings.py; also: sloth-center --kcm <page>). fromMore: a row of
    // More settings' list.
    function openKcm(kcm, args, name, fromMore) {
        leaveKdePage(() => {
            const kdeIndex = Math.max(0, modules.findIndex(m => m.id === "kde"));
            const own = modules.findIndex(m => m.kcm === kcm);
            // opened by a button of a Sloth Center page (e.g. Drivers and hardware's Bluetooth): Back returns there
            const from = !fromMore && pageStack.items.length && pageStack.items[0].kcm === undefined
                         && !modules[shownIndex].more && modules[shownIndex].id !== "kde" ? shownIndex : -1;
            let backTo = null;
            if (fromMore || (own < 0 && from < 0)) {
                // More settings' row (also `systemsettings <page>`): the sidebar shows that list, the row lit
                moreMode = true;
                moreSelected = kcm;
                currentIndex = kdeIndex;
            } else if (own >= 0) {
                // a page of its own in the sidebar (Bluetooth, Display, Sound): that row is lit, no Back button
                moreMode = false;
                currentIndex = own;
            } else {
                currentIndex = from;
                backTo = () => root.openModule(from);
            }
            pageStack.clear();
            pageStack.push(Qt.resolvedUrl("KcmPage.qml"), {
                kcm: kcm, kcmArgs: args || "", kcmName: name || (own >= 0 ? modules[own].name : ""), backTo: backTo
            });
        });
    }

    Connections {
        target: kde
        function onOpenRequested(page, args) {
            root.openKcm(page, args, "");
            root.raise();
            root.requestActivate();
        }
    }

    // Sloth Center started again (single_instance.py): this window shows what it asked for and comes forward.
    // Without a page: only forward, the page shown stays.
    Connections {
        target: instance
        function onOpenRequested(page, kcm, kcmArgs, game) {
            if (kcm)     // as at start: its own row, or More settings' list (not "Back" to the page shown now)
                root.openKcm(kcm, kcmArgs, "", !modules.some(m => m.kcm === kcm));
            else if (game) {
                root.openModuleById("games");
                Qt.callLater(() => {
                    const p = pageStack.items.length ? pageStack.items[0] : null;
                    if (p && typeof p.openGame === "function")
                        p.openGame(game);
                });
            }
            else if (page && modules.some(m => m.id === page && m.ready))
                root.openModuleById(page);
            if (root.visibility === Window.Minimized || root.visibility === Window.Hidden)
                root.showNormal();
            root.raise();
            root.requestActivate();
        }
    }

    Kirigami.PromptDialog {
        id: unsavedDialog
        title: L.t("Apply the changes?")
        subtitle: L.t("The settings on this page have changed. Apply them before you leave the page?")
        standardButtons: Kirigami.Dialog.Apply | Kirigami.Dialog.Discard | Kirigami.Dialog.Cancel
        onApplied: {
            pageStack.items[0].view.save();
            close();
            const then = root.pendingLeave;
            root.pendingLeave = null;
            if (then)
                then();
        }
        onDiscarded: {
            close();
            const then = root.pendingLeave;
            root.pendingLeave = null;
            if (then)
                then();
        }
        onRejected: root.pendingLeave = null
    }

    function showModule(index) {
        const m = modules[index];
        if (m.kcm) {  // a KDE page: inside (openKcm, through kde_settings.py) or in its own window
            kde.open(m.kcm);
            return;
        }
        shownIndex = index;
        currentIndex = m.more ? modules.findIndex(x => x.id === "kde") : m.under ? modules.findIndex(x => x.id === m.under) : index;
        if (m.more || m.id === "kde") {  // More settings: the sidebar shows its list
            moreMode = true;
            moreSelected = m.more ? m.id : "";
        } else {
            moreMode = false;
        }
        pageStack.clear();
        if (m.ready) {
            if (["status", "disks", "help", "kde", "apps"].includes(m.id))
                pageStack.push(Qt.resolvedUrl(m.page), { navigation: root });
            else
                pageStack.push(Qt.resolvedUrl(m.page));
        } else {
            pageStack.push(comingSoon, { module: m });
        }
    }

    // From another page (Help): opens a module by its id
    function openModuleById(id) {
        const index = modules.findIndex(m => m.id === id);
        if (index >= 0)
            openModule(index);
    }

    globalDrawer: Kirigami.OverlayDrawer {
        edge: Qt.LeftEdge
        modal: false
        handleVisible: false
        // narrowed to icons with the button at its top (the choice is kept)
        readonly property bool collapsed: uiSettings.sidebarCollapsed
        width: collapsed ? Kirigami.Units.iconSizes.medium + Kirigami.Units.largeSpacing * 4 : Kirigami.Units.gridUnit * 14
        Behavior on width { NumberAnimation { duration: Kirigami.Units.shortDuration } }
        leftPadding: 0
        rightPadding: 0
        topPadding: 0
        bottomPadding: 0

        contentItem: ColumnLayout {
            spacing: 0

            // The logo and the name in a box of their own: the list below scrolls under it, never over it
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: drawerHeader.implicitHeight + Kirigami.Units.largeSpacing * 2
                z: 1
                color: Kirigami.Theme.backgroundColor
                RowLayout {
                    id: drawerHeader
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        visible: !root.globalDrawer.collapsed
                        source: "sloth-os"
                        implicitWidth: Kirigami.Units.iconSizes.large
                        implicitHeight: Kirigami.Units.iconSizes.large
                    }
                    Kirigami.Heading {
                        visible: !root.globalDrawer.collapsed
                        text: L.t("Sloth Center")
                        level: 2
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    QQC2.ToolButton {
                        Layout.alignment: Qt.AlignHCenter
                        icon.name: root.globalDrawer.collapsed
                                   ? (root.LayoutMirroring.enabled ? "sidebar-collapse-right" : "sidebar-expand-left")
                                   : (root.LayoutMirroring.enabled ? "sidebar-expand-right" : "sidebar-collapse-left")
                        text: root.globalDrawer.collapsed ? L.t("Show sidebar") : L.t("Hide sidebar")
                        display: QQC2.AbstractButton.IconOnly
                        QQC2.ToolTip.visible: hovered
                        QQC2.ToolTip.text: text
                        onClicked: uiSettings.sidebarCollapsed = !uiSettings.sidebarCollapsed
                    }
                }
            }
            Kirigami.Separator { Layout.fillWidth: true }

            // Back to the everyday list (More settings) and the search
            ColumnLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.smallSpacing
                QQC2.ItemDelegate {
                    visible: root.moreMode
                    Layout.fillWidth: true
                    icon.name: root.LayoutMirroring.enabled ? "go-next" : "go-previous"
                    text: L.t("Back")
                    font.bold: true
                    display: root.globalDrawer.collapsed ? QQC2.AbstractButton.IconOnly : QQC2.AbstractButton.TextBesideIcon
                    QQC2.ToolTip.visible: root.globalDrawer.collapsed && hovered
                    QQC2.ToolTip.text: text
                    onClicked: root.leaveMore()
                }
                Kirigami.SearchField {
                    id: searchField
                    objectName: "search"
                    visible: !root.globalDrawer.collapsed
                    Layout.fillWidth: true
                    placeholderText: L.t("Search settings…")
                    onTextChanged: {
                        root.filter = text;
                        root.searchSelected = "";
                        moduleList.positionViewAtBeginning();
                    }
                }
                // narrowed to icons: the search widens the list again
                QQC2.ToolButton {
                    visible: root.globalDrawer.collapsed
                    Layout.alignment: Qt.AlignHCenter
                    icon.name: "edit-find"
                    text: L.t("Search settings…")
                    display: QQC2.AbstractButton.IconOnly
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.text: text
                    onClicked: root.focusSearch()
                }
                QQC2.Label {
                    visible: (root.searching ? root.searchResults.length === 0 : root.moreMode && root.moreEntries.length === 0)
                             && !root.globalDrawer.collapsed
                    Layout.fillWidth: true
                    Layout.margins: Kirigami.Units.largeSpacing
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: catalogLoader.status === Loader.Error ? L.t("The list of settings could not be loaded.")
                                                                : L.t("No setting matches your search.")
                }
            }

            QQC2.ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ListView {
                    id: moduleList
                    clip: true          // the rows never draw over the logo box above or the guide button below
                    model: root.searching ? root.searchResults : root.moreMode ? root.moreEntries : root.modules
                    section.property: "section"
                    // a small title above each group (none above the everyday group and More settings; a line instead)
                    section.delegate: Item {
                        required property string section
                        width: ListView.view.width
                        readonly property bool ownTitles: root.searching || root.moreMode  // KDE's topics
                        readonly property string title: ownTitles ? section : root.sectionNames[section] || ""
                        height: !ownTitles && (section === "daily" || section === "zmore") ? 0
                              : title === "" || root.globalDrawer.collapsed ? Kirigami.Units.largeSpacing
                              : sectionLabel.implicitHeight + Kirigami.Units.largeSpacing * 2
                        Kirigami.Separator {
                            visible: parent.height > 0
                            anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: Kirigami.Units.smallSpacing / 2 }
                        }
                        QQC2.Label {
                            id: sectionLabel
                            visible: parent.title !== "" && !root.globalDrawer.collapsed
                            anchors { left: parent.left; bottom: parent.bottom; leftMargin: Kirigami.Units.largeSpacing; bottomMargin: Kirigami.Units.smallSpacing }
                            text: parent.title
                            font.bold: true
                            opacity: 0.6
                            font.pointSize: Kirigami.Theme.smallFont.pointSize
                        }
                    }
                    delegate: QQC2.ItemDelegate {
                        required property var modelData
                        required property int index
                        width: ListView.view.width
                        visible: root.searching || (root.moreMode ? true : !modelData.more && !modelData.under)
                        height: visible ? implicitHeight : 0
                        highlighted: root.searching ? modelData.id === root.searchSelected
                                   : root.moreMode ? modelData.id === root.moreSelected : index === root.currentIndex
                        icon.name: modelData.icon || "preferences-other"
                        text: modelData.name
                        display: root.globalDrawer.collapsed ? QQC2.AbstractButton.IconOnly : QQC2.AbstractButton.TextBesideIcon
                        // collapsed: the name; in More settings also what the page is for (KDE's own description)
                        QQC2.ToolTip.visible: hovered && (root.globalDrawer.collapsed || (modelData.description || "") !== "")
                        QQC2.ToolTip.text: root.globalDrawer.collapsed ? modelData.name : modelData.description || ""
                        QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                        onClicked: root.searching || root.moreMode ? root.openEntry(modelData) : root.openModule(index)
                    }
                }
            }

        }
    }

    QQC2.Popup {
        id: guideDialog
        parent: QQC2.Overlay.overlay
        x: 0
        y: 0
        width: root.width
        height: root.height
        padding: 0
        modal: true
        dim: false
        closePolicy: QQC2.Popup.CloseOnEscape
        background: null
        onClosed: {
            guide.markSeen();
            moduleList.positionViewAtBeginning();  // the guide scrolled the list: the everyday rows first again
        }

        readonly property var step: root.guideSteps[root.guideStep]
        readonly property bool last: root.guideStep === root.guideSteps.length - 1
        // The lit-up area: the step's pages in the list, together
        property real spotX: 0
        property real spotY: 0
        property real spotW: 0
        property real spotH: 0
        Behavior on spotY { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.InOutCubic } }
        Behavior on spotH { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.InOutCubic } }

        function place() {
            const rows = guideDialog.step.modules.map(id => root.modules.findIndex(m => m.id === id)).filter(i => i >= 0);
            if (!rows.length)
                return;
            // scroll the list so that every page of the step can be seen
            moduleList.positionViewAtIndex(Math.max(...rows), ListView.Contain);
            moduleList.positionViewAtIndex(Math.min(...rows), ListView.Contain);
            let top = Infinity, bottom = -Infinity, left = Infinity, right = -Infinity;
            for (const i of rows) {
                const item = moduleList.itemAtIndex(i);
                if (!item)
                    continue;
                const p = item.mapToItem(spot, 0, 0);
                top = Math.min(top, p.y);
                bottom = Math.max(bottom, p.y + item.height);
                left = Math.min(left, p.x);
                right = Math.max(right, p.x + item.width);
            }
            if (top === Infinity) {
                // the list is not laid out yet (the window is just opening): a moment later
                placeAgain.restart();
                return;
            }
            guideDialog.spotX = left;
            guideDialog.spotY = top;
            guideDialog.spotW = right - left;
            guideDialog.spotH = bottom - top;
        }

        Timer {
            id: placeAgain
            interval: 150
            onTriggered: if (guideDialog.visible) guideDialog.place()
        }

        Connections {
            target: root
            function onGuideStepChanged() { if (guideDialog.visible) Qt.callLater(guideDialog.place) }
            function onWidthChanged() { if (guideDialog.visible) Qt.callLater(guideDialog.place) }
            function onHeightChanged() { if (guideDialog.visible) Qt.callLater(guideDialog.place) }
        }

        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Kirigami.Units.longDuration } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Kirigami.Units.shortDuration } }

        contentItem: Item {
            id: spot
            readonly property color shade: Qt.rgba(0, 0, 0, 0.62)

            // Everything outside the lit-up area is dark (four pieces around it); clicks do not go through
            MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: wheel => wheel.accepted = true }
            Rectangle { color: spot.shade; x: 0; y: 0; width: parent.width; height: guideDialog.spotY }
            Rectangle {
                color: spot.shade; x: 0; y: guideDialog.spotY + guideDialog.spotH
                width: parent.width; height: Math.max(0, parent.height - y)
            }
            Rectangle { color: spot.shade; x: 0; y: guideDialog.spotY; width: guideDialog.spotX; height: guideDialog.spotH }
            Rectangle {
                color: spot.shade; x: guideDialog.spotX + guideDialog.spotW; y: guideDialog.spotY
                width: Math.max(0, parent.width - x); height: guideDialog.spotH
            }

            // A gently pulsing frame around the pages
            Rectangle {
                x: guideDialog.spotX - 2
                y: guideDialog.spotY - 2
                width: guideDialog.spotW + 4
                height: guideDialog.spotH + 4
                radius: Kirigami.Units.cornerRadius
                color: "transparent"
                border.width: 2
                border.color: Kirigami.Theme.highlightColor
                SequentialAnimation on opacity {
                    running: guideDialog.visible
                    loops: Animation.Infinite
                    NumberAnimation { from: 1; to: 0.35; duration: 900; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 0.35; to: 1; duration: 900; easing.type: Easing.InOutSine }
                }
            }

            // The explanation next to the pages, with a small pointer towards them
            Rectangle {
                id: bubble
                readonly property real margin: Kirigami.Units.gridUnit
                x: Math.min(guideDialog.spotX + guideDialog.spotW + margin, parent.width - width - Kirigami.Units.smallSpacing)
                y: Math.max(Kirigami.Units.smallSpacing,
                            Math.min(guideDialog.spotY + guideDialog.spotH / 2 - height / 2,
                                     parent.height - height - Kirigami.Units.smallSpacing))
                width: Math.min(Kirigami.Units.gridUnit * 24,
                                parent.width - guideDialog.spotX - guideDialog.spotW - margin - Kirigami.Units.smallSpacing)
                height: bubbleContent.implicitHeight + Kirigami.Units.largeSpacing * 2
                radius: Kirigami.Units.cornerRadius * 2
                color: Kirigami.Theme.backgroundColor
                border.width: 1
                border.color: Kirigami.Theme.highlightColor
                Behavior on y { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.InOutCubic } }

                Rectangle {
                    width: Kirigami.Units.gridUnit * 0.8
                    height: width
                    rotation: 45
                    x: -width / 2
                    y: Math.max(bubble.radius, Math.min(guideDialog.spotY + guideDialog.spotH / 2 - bubble.y - height / 2,
                                                        bubble.height - height - bubble.radius))
                    color: bubble.color
                    border.width: 1
                    border.color: bubble.border.color
                    z: -1
                }

                ColumnLayout {
                    id: bubbleContent
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Kirigami.Units.largeSpacing }
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Label {
                        opacity: 0.7
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: L.t("A quick tour of Sloth Center") + " · " + (root.guideStep + 1) + "/" + root.guideSteps.length
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        level: 2
                        wrapMode: Text.Wrap
                        text: guideDialog.step.title
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: guideDialog.step.text
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        QQC2.Button {
                            text: L.t("Skip guide")
                            flat: true
                            onClicked: guideDialog.close()
                        }
                        Item { Layout.fillWidth: true }
                        QQC2.Button {
                            visible: root.guideStep > 0
                            text: L.t("Back")
                            onClicked: root.guideStep--
                        }
                        QQC2.Button {
                            text: guideDialog.last ? L.t("Done") : L.t("Next")
                            highlighted: true
                            focus: true
                            onClicked: {
                                if (guideDialog.last)
                                    guideDialog.close();
                                else
                                    root.guideStep++;
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: comingSoon
        Kirigami.Page {
            property var module
            title: module ? module.name : ""
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                icon.name: parent.module ? parent.module.icon : ""
                text: L.t("Coming soon")
                explanation: parent.module ? parent.module.description : ""
            }
        }
    }

    // The page to open: sloth-center --page <ID> (e.g. from the NVIDIA notification: drivers), or a KDE page:
    // sloth-center --kcm <page> (from `systemsettings <page>`, /usr/libexec/sloth-os/systemsettings-wrapper)
    Component.onCompleted: {
        if (startKcm)
            openKcm(startKcm, startKcmArgs, "");
        else
        {
            // without --page: System status (not the first row: the network row opens a window of its own)
            const start = modules.findIndex(m => m.id === startPage && m.ready);
            openModule(start >= 0 ? start : modules.findIndex(m => m.id === "status"));
            // the list scrolls to the lit row; on a short screen that hid the everyday rows at the top
            if (start < 0)
                Qt.callLater(() => moduleList.positionViewAtBeginning());
        }
        if (!guide.seen)
            openGuide();
    }
}
