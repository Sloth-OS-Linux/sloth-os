// More settings: everything that is not an everyday setting. First Sloth OS's own advanced pages (the modules with
// "more: true" in Main.qml), then every KDE settings page (keyboard, mouse, fonts, windows, shortcuts…) in KDE's own
// groups and names, opened inside Sloth Center (kde_settings.py). One settings app: KDE's System Settings is not
// needed. KDE pages that a Sloth Center page already covers ("covered") show only when searching.
//
// Four ways to show it, the user picks one (kept in Main.qml's ui settings):
//   topics   big tiles per topic, a topic's settings as icons after a click (like Windows' Control Panel) – the
//            default
//   icons    every setting as an icon, in groups (like the Mac's old System Preferences)
//   sidebar  the topics on the left, the chosen topic's settings on the right (like KDE's System Settings)
//   list     everything in one list with descriptions
// While searching, the matches are always shown as a list.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: page
    property var navigation: null
    title: L.t("More settings")
    padding: 0

    readonly property var kdePages: pagesLoader.status === Loader.Ready ? pagesLoader.item.modules : []
    readonly property var kdeGroups: kdePages.length ? kde.groups(kdePages) : []
    readonly property var slothGroup: ({
        id: "sloth", name: "Sloth OS", icon: "sloth-os",
        pages: navigation ? navigation.modules.filter(m => m.more).map(m => ({
            id: m.id, name: m.name, icon: m.icon, description: "", keywords: [], sloth: true })) : []
    })
    readonly property var allGroups: [slothGroup].concat(kdeGroups)

    property string filter: ""
    property string topic: ""
    readonly property string view: navigation ? navigation.ui.kdeView : "topics"
    readonly property bool searching: filter.trim() !== ""
    // the groups with the settings to show now (covered KDE pages only when searching)
    readonly property var shownGroups: allGroups.map(g => ({
        id: g.id || "other", name: g.name || L.t("Other"), icon: g.icon || "preferences-other",
        pages: g.pages.filter(p => (!p.covered || searching) && matches(p))
    })).filter(g => g.pages.length > 0)
    readonly property var currentGroup: (topic !== "" ? shownGroups.find(g => g.id === topic) : null)
        || (view === "sidebar" && shownGroups.length ? shownGroups[0] : null)

    // where the user was (back from a KDE page brings them here again)
    onFilterChanged: if (navigation) navigation.kdeState = { filter: filter, topic: topic }
    onTopicChanged: if (navigation) navigation.kdeState = { filter: filter, topic: topic }
    Component.onCompleted: {
        if (navigation) {
            const state = navigation.kdeState;
            search.text = state.filter || "";
            topic = state.topic || "";
        }
    }

    function matches(p) {
        const f = filter.trim().toLowerCase();
        if (!f)
            return true;
        return [p.name, p.description, p.id].concat(p.keywords || []).some(s => (s || "").toLowerCase().includes(f));
    }

    function openEntry(p) {
        if (p.sloth)
            page.navigation.openModuleById(p.id);
        else if (p.widget)
            kde.openWindow(p.id);
        else if (page.navigation)
            page.navigation.openKcm(p.id, "", p.name);
    }

    function setView(v) {
        if (page.navigation)
            page.navigation.ui.kdeView = v;
    }

    Loader {
        id: pagesLoader
        source: "KcmCatalogView.qml"
        visible: false
    }

    header: QQC2.ToolBar {
        contentItem: RowLayout {
            spacing: Kirigami.Units.smallSpacing
            QQC2.ToolButton {
                visible: page.view === "topics" && page.topic !== "" && !page.searching
                icon.name: page.LayoutMirroring.enabled ? "go-next" : "go-previous"
                text: L.t("All topics")
                onClicked: page.topic = ""
            }
            Kirigami.SearchField {
                id: search
                objectName: "kdeSearch"
                Layout.fillWidth: true
                placeholderText: L.t("Search settings…")
                onTextChanged: page.filter = text
            }
            Repeater {
                model: [
                    { id: "topics", icon: "view-grid", name: L.t("Topics") },
                    { id: "icons", icon: "view-list-icons", name: L.t("Icons") },
                    { id: "sidebar", icon: "view-split-left-right", name: L.t("Sidebar") },
                    { id: "list", icon: "view-list-details", name: L.t("List") }
                ]
                delegate: QQC2.ToolButton {
                    required property var modelData
                    checkable: true
                    checked: page.view === modelData.id
                    icon.name: modelData.icon
                    text: modelData.name
                    display: QQC2.AbstractButton.IconOnly
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.text: modelData.name
                    onClicked: page.setView(modelData.id)
                }
            }
        }
    }

    Kirigami.InlineMessage {
        id: loadError
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Kirigami.Units.largeSpacing }
        visible: pagesLoader.status === Loader.Error
        type: Kirigami.MessageType.Warning
        text: L.t("The list of settings could not be loaded.")
    }

    Loader {
        anchors.fill: parent
        anchors.topMargin: loadError.visible ? loadError.height + Kirigami.Units.largeSpacing * 2 : 0
        sourceComponent: page.searching || page.view === "list" ? listView
                       : page.view === "icons" ? iconsView
                       : page.view === "sidebar" ? sidebarView
                       : page.topic !== "" && page.currentGroup ? topicView : topicsView
    }

    Kirigami.PlaceholderMessage {
        anchors.centerIn: parent
        width: parent.width - Kirigami.Units.gridUnit * 4
        visible: page.searching && page.shownGroups.length === 0
        icon.name: "edit-find"
        text: L.t("No setting matches your search.")
    }

    // --- One setting as a row (name and description) and as an icon -------------------------------------------
    Component {
        id: rowDelegate
        QQC2.ItemDelegate {
            id: row
            required property var modelData
            Layout.fillWidth: true
            onClicked: page.openEntry(modelData)
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: row.modelData.icon || "preferences-other"
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: Kirigami.Units.iconSizes.medium
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    QQC2.Label {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: row.modelData.name
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        visible: text !== ""
                        opacity: 0.7
                        font: Kirigami.Theme.smallFont
                        text: row.modelData.description || ""
                    }
                }
                Kirigami.Icon {
                    visible: row.modelData.widget === true
                    source: "window-new"
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: Kirigami.Units.iconSizes.small
                    QQC2.ToolTip.visible: hover.hovered
                    QQC2.ToolTip.text: L.t("Opens in its own window")
                    HoverHandler { id: hover }
                }
            }
        }
    }

    Component {
        id: iconDelegate
        QQC2.ItemDelegate {
            id: tile
            required property var modelData
            width: Kirigami.Units.gridUnit * 7
            height: Kirigami.Units.gridUnit * 6
            onClicked: page.openEntry(modelData)
            QQC2.ToolTip.visible: hovered && (modelData.description || "") !== ""
            QQC2.ToolTip.text: modelData.description || ""
            QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Icon {
                    Layout.alignment: Qt.AlignHCenter
                    source: tile.modelData.icon || "preferences-other"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    text: tile.modelData.name
                }
            }
        }
    }

    Component {
        id: groupHeading
        RowLayout {
            id: heading
            property var group: ({ name: "", icon: "" })
            Layout.topMargin: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
            Kirigami.Icon {
                source: heading.group.icon
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: Kirigami.Units.iconSizes.smallMedium
            }
            Kirigami.Heading { level: 3; text: heading.group.name }
        }
    }

    // The open topic's title, big (after a tile, and on the right in the sidebar view)
    Component {
        id: topicHeader
        RowLayout {
            id: bigHeading
            property var group: ({ name: "", icon: "" })
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon {
                source: bigHeading.group.icon
                implicitWidth: Kirigami.Units.iconSizes.huge
                implicitHeight: Kirigami.Units.iconSizes.huge
            }
            Kirigami.Heading {
                Layout.fillWidth: true
                level: 1
                wrapMode: Text.Wrap
                text: bigHeading.group.name
            }
        }
    }

    // --- Topics: big tiles (the default) ----------------------------------------------------------------------
    Component {
        id: topicsView
        QQC2.ScrollView {
            id: topicsScroll
            contentWidth: availableWidth
            implicitWidth: Kirigami.Units.gridUnit * 20   // fixed: the Loader sizes it (no binding loop)
            ColumnLayout {
                width: topicsScroll.availableWidth
                spacing: Kirigami.Units.largeSpacing
                QQC2.Label {
                    Layout.fillWidth: true
                    Layout.margins: Kirigami.Units.largeSpacing
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Every other setting of the desktop: keyboard, mouse and touchpad, fonts, windows, shortcuts, the login screen and more. Changes are made with the Apply button under each page.")
                }
                Flow {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing
                    Layout.rightMargin: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.largeSpacing
                    Repeater {
                        model: page.shownGroups
                        delegate: QQC2.ItemDelegate {
                            id: topicTile
                            required property var modelData
                            width: Kirigami.Units.gridUnit * 16
                            height: Kirigami.Units.gridUnit * 4.5
                            onClicked: page.topic = modelData.id
                            background: Rectangle {
                                radius: Kirigami.Units.cornerRadius
                                color: topicTile.hovered ? Kirigami.Theme.hoverColor : Kirigami.Theme.alternateBackgroundColor
                                border.color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
                            }
                            contentItem: RowLayout {
                                spacing: Kirigami.Units.largeSpacing
                                Kirigami.Icon {
                                    source: topicTile.modelData.icon
                                    implicitWidth: Kirigami.Units.iconSizes.large
                                    implicitHeight: Kirigami.Units.iconSizes.large
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        font.bold: true
                                        text: topicTile.modelData.name
                                    }
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        wrapMode: Text.Wrap
                                        maximumLineCount: 2
                                        elide: Text.ElideRight
                                        opacity: 0.7
                                        font: Kirigami.Theme.smallFont
                                        text: topicTile.modelData.pages.slice(0, 4).map(p => p.name).join(", ")
                                              + (topicTile.modelData.pages.length > 4 ? "…" : "")
                                    }
                                }
                            }
                        }
                    }
                }
                Item { Layout.preferredHeight: Kirigami.Units.largeSpacing }
            }
        }
    }

    // --- One topic's settings (after a tile): icons, as the tiles were ---------------------------------------
    Component {
        id: topicView
        QQC2.ScrollView {
            id: topicScroll
            contentWidth: availableWidth
            implicitWidth: Kirigami.Units.gridUnit * 20   // fixed: the Loader sizes it (no binding loop)
            ColumnLayout {
                width: topicScroll.availableWidth
                spacing: Kirigami.Units.largeSpacing
                Loader {
                    Layout.fillWidth: true
                    Layout.margins: Kirigami.Units.largeSpacing
                    Layout.bottomMargin: 0
                    sourceComponent: topicHeader
                    onLoaded: item.group = Qt.binding(() => page.currentGroup || { name: "", icon: "" })
                }
                Flow {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing
                    Layout.rightMargin: Kirigami.Units.largeSpacing
                    Repeater {
                        model: page.currentGroup ? page.currentGroup.pages : []
                        delegate: iconDelegate
                    }
                }
            }
        }
    }

    // --- Icons: every setting as an icon, in groups ------------------------------------------------------------
    Component {
        id: iconsView
        QQC2.ScrollView {
            id: iconsScroll
            contentWidth: availableWidth
            implicitWidth: Kirigami.Units.gridUnit * 20   // fixed: the Loader sizes it (no binding loop)
            ColumnLayout {
                width: iconsScroll.availableWidth
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: page.shownGroups
                    delegate: ColumnLayout {
                        id: iconGroup
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.leftMargin: Kirigami.Units.largeSpacing
                        Layout.rightMargin: Kirigami.Units.largeSpacing
                        Loader {
                            sourceComponent: groupHeading
                            onLoaded: item.group = iconGroup.modelData
                        }
                        Flow {
                            Layout.fillWidth: true
                            Repeater {
                                model: iconGroup.modelData.pages
                                delegate: iconDelegate
                            }
                        }
                        Kirigami.Separator { Layout.fillWidth: true }
                    }
                }
            }
        }
    }

    // --- Sidebar: the topics on the left, the settings on the right --------------------------------------------
    Component {
        id: sidebarView
        RowLayout {
            spacing: 0
            QQC2.ScrollView {
                Layout.fillHeight: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 13
                ListView {
                    model: page.shownGroups
                    delegate: QQC2.ItemDelegate {
                        required property var modelData
                        width: ListView.view.width
                        highlighted: page.currentGroup !== null && page.currentGroup.id === modelData.id
                        icon.name: modelData.icon
                        text: modelData.name
                        onClicked: page.topic = modelData.id
                    }
                }
            }
            Kirigami.Separator { Layout.fillHeight: true }
            QQC2.ScrollView {
                id: sideScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
            implicitWidth: Kirigami.Units.gridUnit * 20   // fixed: the Loader sizes it (no binding loop)
                ColumnLayout {
                    width: sideScroll.availableWidth
                    spacing: 0
                    Loader {
                        Layout.fillWidth: true
                        Layout.margins: Kirigami.Units.largeSpacing
                        sourceComponent: topicHeader
                        onLoaded: item.group = Qt.binding(() => page.currentGroup || { name: "", icon: "" })
                    }
                    Repeater {
                        model: page.currentGroup ? page.currentGroup.pages : []
                        delegate: rowDelegate
                    }
                }
            }
        }
    }

    // --- List: everything, with descriptions (also the search results) ----------------------------------------
    Component {
        id: listView
        QQC2.ScrollView {
            id: listScroll
            contentWidth: availableWidth
            implicitWidth: Kirigami.Units.gridUnit * 20   // fixed: the Loader sizes it (no binding loop)
            ColumnLayout {
                width: listScroll.availableWidth
                spacing: 0
                QQC2.Label {
                    Layout.fillWidth: true
                    Layout.margins: Kirigami.Units.largeSpacing
                    visible: !page.searching
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Every other setting of the desktop: keyboard, mouse and touchpad, fonts, windows, shortcuts, the login screen and more. Changes are made with the Apply button under each page.")
                }
                Repeater {
                    model: page.shownGroups
                    delegate: ColumnLayout {
                        id: listGroup
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 0
                        Loader {
                            Layout.leftMargin: Kirigami.Units.largeSpacing
                            sourceComponent: groupHeading
                            onLoaded: item.group = listGroup.modelData
                        }
                        Repeater {
                            model: listGroup.modelData.pages
                            delegate: rowDelegate
                        }
                    }
                }
            }
        }
    }
}
