// More settings: every KDE settings page (keyboard, mouse, fonts, windows, shortcuts…), in KDE's own groups and
// names, opened inside Sloth Center (kde_settings.py). One settings app: KDE's System Settings is not needed.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    property var navigation: null
    title: L.t("More settings")

    readonly property var allPages: pagesLoader.status === Loader.Ready ? pagesLoader.item.modules : []
    readonly property var groups: allPages.length ? kde.groups(allPages) : []
    property string filter: ""

    function matches(p) {
        const f = filter.trim().toLowerCase();
        if (!f)
            return true;
        return [p.name, p.description, p.id].concat(p.keywords || []).some(s => (s || "").toLowerCase().includes(f));
    }

    function openPage(p) {
        if (p.widget)
            kde.openWindow(p.id);
        else if (page.navigation)
            page.navigation.openKcm(p.id, "", p.name);
    }

    Loader {
        id: pagesLoader
        source: "KcmCatalogView.qml"
        visible: false
    }

    header: QQC2.ToolBar {
        contentItem: Kirigami.SearchField {
            id: search
            placeholderText: L.t("Search settings…")
            onTextChanged: page.filter = text
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("Every other setting of the desktop: keyboard, mouse and touchpad, fonts, windows, shortcuts, the login screen and more. Changes are made with the Apply button under each page.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: pagesLoader.status === Loader.Error
            type: Kirigami.MessageType.Warning
            text: L.t("The list of settings could not be loaded.")
        }

        Repeater {
            model: page.groups
            delegate: ColumnLayout {
                id: groupItem
                required property var modelData
                readonly property var shown: modelData.pages.filter(p => page.matches(p))
                Layout.fillWidth: true
                visible: shown.length > 0
                spacing: 0

                RowLayout {
                    Layout.topMargin: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Icon {
                        source: groupItem.modelData.icon
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                    }
                    Kirigami.Heading {
                        level: 3
                        text: groupItem.modelData.name || L.t("Other")
                    }
                }

                Repeater {
                    model: groupItem.shown
                    delegate: QQC2.ItemDelegate {
                        id: pageItem
                        required property var modelData
                        Layout.fillWidth: true
                        onClicked: page.openPage(modelData)
                        contentItem: RowLayout {
                            spacing: Kirigami.Units.largeSpacing
                            Kirigami.Icon {
                                source: pageItem.modelData.icon || "preferences-other"
                                implicitWidth: Kirigami.Units.iconSizes.medium
                                implicitHeight: Kirigami.Units.iconSizes.medium
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: pageItem.modelData.name
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    visible: text !== ""
                                    opacity: 0.7
                                    font: Kirigami.Theme.smallFont
                                    text: pageItem.modelData.description
                                }
                            }
                            Kirigami.Icon {
                                visible: pageItem.modelData.widget
                                source: "window-new"
                                implicitWidth: Kirigami.Units.iconSizes.small
                                implicitHeight: Kirigami.Units.iconSizes.small
                                QQC2.ToolTip.visible: hoverHandler.hovered
                                QQC2.ToolTip.text: L.t("Opens in its own window")
                                HoverHandler { id: hoverHandler }
                            }
                        }
                    }
                }
            }
        }

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: page.filter !== "" && page.groups.every(g => !g.pages.some(p => page.matches(p)))
            icon.name: "edit-find"
            text: L.t("No setting matches your search.")
        }
    }
}
