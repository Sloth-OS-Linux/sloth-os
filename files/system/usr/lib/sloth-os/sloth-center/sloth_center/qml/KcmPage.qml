// A KDE settings page inside Sloth Center (kde_settings.py): the page with its own header and sub-pages, and the
// Apply / Reset / Defaults buttons under it, as in KDE's System Settings. If it can't be shown here, it opens in its
// own window.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: page
    property string kcm
    property string kcmArgs
    property string kcmName
    property bool inWindow: false
    readonly property var view: host.status === Loader.Ready ? host.item : null

    title: view && view.title ? view.title : kcmName
    padding: 0
    // the KDE page brings its own header (title, its buttons, back from its sub-pages)
    globalToolBarStyle: inWindow ? Kirigami.ApplicationHeaderStyle.Auto : Kirigami.ApplicationHeaderStyle.None

    function openInWindow() {
        if (inWindow)
            return;
        inWindow = true;
        kde.openWindow(kcm);
    }

    Loader {
        id: host
        anchors.fill: parent
        visible: !page.inWindow
        source: "KcmHostView.qml"
        onLoaded: {
            item.arguments = page.kcmArgs ? page.kcmArgs.split(" ") : [];
            item.module = page.kcm;
            if (item.error)
                page.openInWindow();
        }
        onStatusChanged: if (status === Loader.Error) page.openInWindow()
    }
    Connections {
        target: page.view
        function onStateChanged() {
            if (page.view.error)
                page.openInWindow();
        }
    }

    Kirigami.PlaceholderMessage {
        anchors.centerIn: parent
        width: parent.width - Kirigami.Units.gridUnit * 4
        visible: page.inWindow
        icon.name: "window-new"
        text: L.t("This setting opened in its own window.")
        helpfulAction: Kirigami.Action {
            text: L.t("Open it again")
            icon.name: "window-new"
            onTriggered: kde.openWindow(page.kcm)
        }
    }

    footer: QQC2.ToolBar {
        visible: !page.inWindow && page.view !== null && page.view.loaded && (page.view.hasApply || page.view.hasDefaults)
        contentItem: RowLayout {
            QQC2.Button {
                visible: page.view !== null && page.view.hasDefaults
                enabled: page.view !== null && !page.view.representsDefaults
                text: L.t("Defaults")
                icon.name: "edit-reset"
                onClicked: page.view.defaults()
            }
            Item { Layout.fillWidth: true }
            QQC2.Button {
                visible: page.view !== null && page.view.hasApply
                enabled: page.view !== null && page.view.needsSave
                text: L.t("Reset")
                icon.name: "edit-undo"
                onClicked: page.view.reset()
            }
            QQC2.Button {
                visible: page.view !== null && page.view.hasApply
                enabled: page.view !== null && page.view.needsSave
                highlighted: enabled
                text: L.t("Apply")
                icon.name: "dialog-ok-apply"
                onClicked: page.view.save()
            }
        }
    }
}
