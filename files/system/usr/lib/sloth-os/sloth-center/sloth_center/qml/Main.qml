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
        { id: "winprograms", name: L.t("Windows-programok"), icon: "application-x-ms-dos-executable", page: "WinProgramsPage.qml", ready: true },
        { id: "games", name: L.t("Játékok"), icon: "input-gamepad", page: "GamesPage.qml", ready: true },
        { id: "drivers", name: L.t("Driverek és hardver"), icon: "preferences-devices-cpu", page: "DriversPage.qml", ready: true },
        { id: "services", name: L.t("Szolgáltatások"), icon: "preferences-system-services", page: "ServicesPage.qml", ready: true },
        { id: "accounts", name: L.t("Fiók és biztonság"), icon: "preferences-system-users", page: "AccountsPage.qml", ready: true },
        { id: "health", name: L.t("Rendszer egészség"), icon: "dialog-information", page: "HealthPage.qml", ready: true },
        { id: "disks", name: L.t("Lemezek"), icon: "drive-harddisk", page: "DisksPage.qml", ready: true },
        { id: "containers", name: L.t("Fejlesztői környezetek"), icon: "utilities-terminal", page: "ContainersPage.qml", ready: true },
        { id: "advanced", name: L.t("Haladó beállítások"), icon: "configure", page: "AdvancedPage.qml", ready: true },
        { id: "devpanel", name: L.t("Fejlesztői pult"), icon: "applications-development", ready: false,
          description: L.t("A Sloth OS fejlesztéséhez: build indítása és állapota, tesztelés.") }
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

    Component.onCompleted: openModule(0)
}
