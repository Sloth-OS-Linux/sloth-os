// Sloth Központ – főablak: bal oldalon a modulok, jobbra a kiválasztott oldal.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: L.t("Sloth Központ")
    visible: true
    width: Kirigami.Units.gridUnit * 56
    height: Kirigami.Units.gridUnit * 38
    minimumWidth: Kirigami.Units.gridUnit * 30
    minimumHeight: Kirigami.Units.gridUnit * 24

    // A modulok listája. A "ready: false" modulok még készülnek (ROADMAP 3. fázis).
    readonly property var modules: [
        { id: "updates", name: L.t("Frissítések"), icon: "system-software-update", page: "UpdatesPage.qml", ready: true },
        { id: "winprograms", name: L.t("Programok"), icon: "application-x-ms-dos-executable", page: "WinProgramsPage.qml", ready: true },
        { id: "games", name: L.t("Játékok"), icon: "input-gamepad", page: "GamesPage.qml", ready: true },
        { id: "drivers", name: L.t("Driverek és hardver"), icon: "preferences-devices-cpu", page: "DriversPage.qml", ready: true },
        { id: "services", name: L.t("Szolgáltatások"), icon: "preferences-system-services", page: "ServicesPage.qml", ready: true },
        { id: "accounts", name: L.t("Fiók és biztonság"), icon: "preferences-system-users", page: "AccountsPage.qml", ready: true },
        { id: "parental", name: L.t("Szülői felügyelet"), icon: "user-group-properties", ready: false,
          description: L.t("Gyerekfiók, korhatár szerinti appok és képernyőidő. Ez a rész egy következő frissítéssel érkezik.") },
        { id: "health", name: L.t("Rendszer egészség"), icon: "dialog-information", page: "HealthPage.qml", ready: true },
        { id: "feedback", name: L.t("Visszajelzés"), icon: "mail-message-new", page: "FeedbackPage.qml", ready: true },
        { id: "backup", name: L.t("Fájlmentés"), icon: "backup", page: "BackupPage.qml", ready: true },
        { id: "disks", name: L.t("Lemezek"), icon: "drive-harddisk", page: "DisksPage.qml", ready: true },
        { id: "containers", name: L.t("Fejlesztői környezetek"), icon: "utilities-terminal", page: "ContainersPage.qml", ready: true },
        { id: "reset", name: L.t("Alaphelyzetbe állítás"), icon: "edit-undo", page: "ResetPage.qml", ready: true },
        { id: "advanced", name: L.t("Haladó beállítások"), icon: "configure", page: "AdvancedPage.qml", ready: true },
        { id: "devpanel", name: L.t("Fejlesztői pult"), icon: "applications-development", page: "DevPanelPage.qml",
          ready: true }
    ]
    property int currentIndex: 0

    function openModule(index) {
        currentIndex = index;
        const m = modules[index];
        pageStack.clear();
        if (m.ready) {
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
                    text: L.t("Sloth Központ")
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
                text: L.t("Hamarosan")
                explanation: parent.module ? parent.module.description : ""
            }
        }
    }

    // A megnyitandó oldal: sloth-center --page <azonosító> (pl. az NVIDIA-értesítésből: drivers)
    Component.onCompleted: openModule(Math.max(0, modules.findIndex(m => m.id === startPage && m.ready)))
}
