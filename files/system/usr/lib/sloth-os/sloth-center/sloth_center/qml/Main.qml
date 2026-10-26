// Sloth Center – main window: the modules on the left, the selected page on the right.
pragma ComponentBehavior: Bound
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

    // The list of modules. Modules with "ready: false" are still being made (ROADMAP phase 3).
    readonly property var modules: [
        { id: "status", name: L.t("System status"), icon: "dialog-information", page: "SystemStatusPage.qml", ready: true },
        { id: "updates", name: L.t("Updates"), icon: "system-software-update", page: "UpdatesPage.qml", ready: true },
        { id: "winprograms", name: L.t("Programs"), icon: "application-x-ms-dos-executable", page: "WinProgramsPage.qml", ready: true },
        { id: "games", name: L.t("Games"), icon: "input-gamepad", page: "GamesPage.qml", ready: true },
        { id: "drivers", name: L.t("Drivers and hardware"), icon: "preferences-devices-cpu", page: "DriversPage.qml", ready: true },
        { id: "services", name: L.t("Services"), icon: "preferences-system-services", page: "ServicesPage.qml", ready: true },
        { id: "accounts", name: L.t("Account and security"), icon: "preferences-system-users", page: "AccountsPage.qml", ready: true },
        { id: "appearance", name: L.t("Appearance"), icon: "preferences-desktop-theme-global", page: "AppearancePage.qml", ready: true },
        { id: "parental", name: L.t("Parental controls"), icon: "user-group-properties", ready: false,
          description: L.t("Child accounts, age-appropriate apps and screen time. This part is coming in a future update.") },
        { id: "health", name: L.t("System health"), icon: "dialog-information", page: "HealthPage.qml", ready: true },
        { id: "feedback", name: L.t("Feedback"), icon: "mail-message-new", page: "FeedbackPage.qml", ready: true },
        { id: "usbguide", name: L.t("Create installation media"), icon: "drive-removable-media-usb", page: "UsbGuidePage.qml", ready: true },
        { id: "backup", name: L.t("File backup"), icon: "backup", page: "BackupPage.qml", ready: true },
        { id: "disks", name: L.t("Disks"), icon: "drive-harddisk", page: "DisksPage.qml", ready: true },
        { id: "containers", name: L.t("Developer environments"), icon: "utilities-terminal", page: "ContainersPage.qml", ready: true },
        { id: "reset", name: L.t("Reset this PC"), icon: "edit-undo", page: "ResetPage.qml", ready: true },
        { id: "advanced", name: L.t("Advanced settings"), icon: "configure", page: "AdvancedPage.qml", ready: true },
        { id: "devpanel", name: L.t("Developer panel"), icon: "applications-development", page: "DevPanelPage.qml",
          ready: true }
    ]
    property int currentIndex: 0
    property int guideStep: 0

    function openGuide() {
        guideStep = 0;
        guideDialog.open();
    }

    function openModule(index) {
        currentIndex = index;
        const m = modules[index];
        pageStack.clear();
        if (m.ready) {
            if (["status", "health", "disks"].includes(m.id))
                pageStack.push(Qt.resolvedUrl(m.page), { navigation: root });
            else
                pageStack.push(Qt.resolvedUrl(m.page));
        } else {
            pageStack.push(comingSoon, { module: m });
        }
    }

    globalDrawer: Kirigami.OverlayDrawer {
        edge: Qt.LeftEdge
        modal: false
        handleVisible: false
        width: Kirigami.Units.gridUnit * 14
        leftPadding: 0
        rightPadding: 0
        topPadding: 0
        bottomPadding: 0

        contentItem: ColumnLayout {
            spacing: 0

            RowLayout {
                Layout.margins: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: "sloth-os"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                Kirigami.Heading {
                    text: L.t("Sloth Center")
                    level: 2
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            QQC2.ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ListView {
                    model: root.modules
                    delegate: QQC2.ItemDelegate {
                        required property var modelData
                        required property int index
                        width: ListView.view.width
                        highlighted: index === root.currentIndex
                        icon.name: modelData.icon
                        text: modelData.name
                        onClicked: root.openModule(index)
                    }
                }
            }

            QQC2.Button {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.smallSpacing
                text: L.t("Open guide")
                icon.name: "help-about"
                onClicked: root.openGuide()
            }
        }
    }

    QQC2.Dialog {
        id: guideDialog
        parent: QQC2.Overlay.overlay
        anchors.centerIn: parent
        modal: true
        title: L.t("A quick tour of Sloth Center")
        standardButtons: QQC2.Dialog.NoButton
        width: Math.min(root.width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 34)
        onClosed: guide.markSeen()

        contentItem: ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Heading {
                Layout.fillWidth: true
                level: 2
                wrapMode: Text.Wrap
                text: [L.t("Keep Sloth OS up to date"), L.t("Find and manage programs"),
                       L.t("Back up files and get help")][root.guideStep]
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: [L.t("The Updates page installs system updates and lets you return to the previous version if an update causes trouble."),
                       L.t("Programs is where you install and start Windows programs. Games has settings for Steam and other game tools."),
                       L.t("File backup shows saved copies of your files. Feedback is the place to ask for help, and Disks can help bring files over from Windows.")][root.guideStep]
            }
            RowLayout {
                Layout.fillWidth: true
                QQC2.Button {
                    text: L.t("Skip guide")
                    onClicked: guideDialog.close()
                }
                Item { Layout.fillWidth: true }
                QQC2.Button {
                    visible: root.guideStep > 0
                    text: L.t("Back")
                    onClicked: root.guideStep--
                }
                QQC2.Button {
                    text: root.guideStep < 2 ? L.t("Next") : L.t("Done")
                    highlighted: true
                    onClicked: {
                        if (root.guideStep < 2)
                            root.guideStep++;
                        else
                            guideDialog.close();
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

    // The page to open: sloth-center --page <ID> (e.g. from the NVIDIA notification: drivers)
    Component.onCompleted: {
        openModule(Math.max(0, modules.findIndex(m => m.id === startPage && m.ready)));
        if (!guide.seen)
            openGuide();
    }
}
