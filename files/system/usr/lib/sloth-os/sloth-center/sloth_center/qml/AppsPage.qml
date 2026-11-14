// Apps: every app installed on the computer, with Open and Remove (installed_apps.py), like the Apps page of
// Windows' Settings. Windows programs have their own page (WinProgramsPage.qml); Get more apps opens Sloth Welcome,
// where the apps are chosen (nothing is preinstalled).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    property var navigation: null
    title: L.t("Apps")

    property string filter: ""
    property var target: null  // the app the Remove question is about
    readonly property var shown: installedApps.apps.filter(a => {
        const f = page.filter.trim().toLowerCase();
        return !f || a.name.toLowerCase().includes(f) || a.id.toLowerCase().includes(f) || a.summary.toLowerCase().includes(f);
    })

    actions: [
        Kirigami.Action {
            text: L.t("Get more apps")
            icon.name: "list-add"
            onTriggered: installedApps.getMore()
        }
    ]

    Component.onCompleted: installedApps.refresh()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("The apps installed on this computer. Windows programs have a page of their own.")
        }
        RowLayout {
            Layout.fillWidth: true
            Kirigami.SearchField {
                Layout.fillWidth: true
                Layout.maximumWidth: Kirigami.Units.gridUnit * 20
                placeholderText: L.t("Search apps…")
                onTextChanged: page.filter = text
            }
            Item { Layout.fillWidth: true }
            QQC2.Button {
                visible: page.navigation !== null
                text: L.t("Windows programs")
                icon.name: "application-x-ms-dos-executable"
                onClicked: page.navigation.openModuleById("winprograms")
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: installedApps.error !== ""
            type: Kirigami.MessageType.Warning
            text: L.tf("Couldn't remove {name}.", { name: installedApps.error })
        }

        QQC2.BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            visible: !installedApps.loaded
            running: visible
        }
        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: installedApps.loaded && installedApps.apps.length === 0
            icon.name: "applications-other"
            text: L.t("No apps installed yet.")
            helpfulAction: Kirigami.Action {
                text: L.t("Get more apps")
                icon.name: "list-add"
                onTriggered: installedApps.getMore()
            }
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: page.shown.length > 0
            contentItem: ColumnLayout {
                spacing: 0
                Repeater {
                    model: page.shown
                    delegate: RowLayout {
                        id: row
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.smallSpacing
                        Layout.bottomMargin: Kirigami.Units.smallSpacing
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: row.modelData.id
                            fallback: "application-x-executable"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: row.modelData.name }
                            QQC2.Label {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                opacity: 0.7
                                font: Kirigami.Theme.smallFont
                                text: [row.modelData.summary, row.modelData.version,
                                       row.modelData.size > 0 ? Qt.locale().formattedDataSize(row.modelData.size, 1) : ""]
                                      .filter(t => t !== "").join(" · ")
                            }
                        }
                        QQC2.BusyIndicator {
                            visible: installedApps.busy === row.modelData.ref
                            running: visible
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: implicitWidth
                        }
                        QQC2.Button {
                            text: L.t("Open")
                            icon.name: "media-playback-start"
                            onClicked: installedApps.open(row.modelData.id)
                        }
                        QQC2.Button {
                            text: L.t("Remove")
                            icon.name: "edit-delete"
                            enabled: installedApps.busy === ""
                            onClicked: { page.target = row.modelData; deleteData.checked = false; removeDialog.open(); }
                        }
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: removeDialog
        title: page.target ? L.tf("Remove {name}?", { name: page.target.name }) : ""
        standardButtons: Kirigami.Dialog.Cancel
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Remove")
                icon.name: "edit-delete"
                onTriggered: {
                    installedApps.remove(page.target.ref, page.target.scope, deleteData.checked);
                    removeDialog.close();
                }
            }
        ]
        QQC2.CheckBox {
            id: deleteData
            text: L.t("Also delete its settings and saved data")
        }
    }
}
