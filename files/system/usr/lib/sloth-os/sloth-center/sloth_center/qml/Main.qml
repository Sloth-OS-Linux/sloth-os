// Sloth Központ – főablak: bal oldalon a modulok, jobbra a kiválasztott oldal.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: "Sloth Központ"
    visible: true
    width: Kirigami.Units.gridUnit * 56
    height: Kirigami.Units.gridUnit * 38
    minimumWidth: Kirigami.Units.gridUnit * 30
    minimumHeight: Kirigami.Units.gridUnit * 24

    // A modulok listája. A "ready: false" modulok még készülnek (ROADMAP 3. fázis).
    readonly property var modules: [
        { id: "updates", name: "Frissítések", icon: "system-software-update", page: "UpdatesPage.qml", ready: true },
        { id: "drivers", name: "Driverek és hardver", icon: "preferences-devices-cpu", ready: false,
          description: "Videókártya, kontrollerek, NVIDIA és AMD/Intel közötti váltás." },
        { id: "services", name: "Szolgáltatások", icon: "preferences-system-services", ready: false,
          description: "A háttérben futó szolgáltatások be- és kikapcsolása." },
        { id: "health", name: "Rendszer egészség", icon: "dialog-information", ready: false,
          description: "Ha valami nem működik: érthető magyarázat a rendszernaplóból." },
        { id: "disks", name: "Lemezek", icon: "drive-harddisk", ready: false,
          description: "Tárhely-használat és lemezellenőrzés." },
        { id: "containers", name: "Fejlesztői környezetek", icon: "utilities-terminal", ready: false,
          description: "Más Linux-rendszerek futtatása dobozban (Distrobox), appok a menübe." },
        { id: "advanced", name: "Haladó beállítások", icon: "configure", ready: false,
          description: "Rendszercsomagok, kernelparaméterek, boot menü és minden, amihez máshol terminál kellene." },
        { id: "devpanel", name: "Fejlesztői pult", icon: "applications-development", ready: false,
          description: "A Sloth OS fejlesztéséhez: build indítása és állapota, tesztelés." }
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
                    text: "Sloth Központ"
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
                text: "Hamarosan"
                explanation: parent.module ? parent.module.description : ""
            }
        }
    }

    Component.onCompleted: openModule(0)
}
