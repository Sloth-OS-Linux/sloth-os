// Windows-programok: mit csináljunk egy .exe-vel? Telepítés / futtatás, folyamatjelzővel.
// A "Wine", "Proton" és "prefix" szavak szándékosan nem szerepelnek sehol.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: exe.name !== "" ? exe.name : "Windows-program"
    visible: true
    width: Kirigami.Units.gridUnit * 30
    height: Kirigami.Units.gridUnit * 20
    minimumWidth: Kirigami.Units.gridUnit * 24
    minimumHeight: Kirigami.Units.gridUnit * 16
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    Connections {
        target: exe
        function onHideWindow() { root.hide(); }
        function onShowWindow() { root.show(); root.raise(); root.requestActivate(); }
    }

    pageStack.initialPage: Kirigami.Page {
        globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None

        StackLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            currentIndex: ["choose", "working", "pick", "error", "running"].indexOf(exe.state)

            // --- Mit csináljunk? -------------------------------------------------
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing * 2
                Item { Layout.fillHeight: true }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        source: exe.iconUrl !== "" ? exe.iconUrl : "application-x-ms-dos-executable"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading {
                            level: 2
                            text: exe.isInstaller ? exe.name + " telepítése" : exe.name
                        }
                        QQC2.Label {
                            Layout.maximumWidth: Kirigami.Units.gridUnit * 18
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: exe.isInstaller
                                  ? "Ez egy Windows-os telepítő. Itt is működik: telepítés után a Start menüben találod."
                                  : "Ez egy Windows-os program. Itt is el tudod indítani."
                        }
                    }
                }
                QQC2.CheckBox {
                    id: addToMenu
                    Layout.alignment: Qt.AlignHCenter
                    visible: !exe.isInstaller
                    text: "Hozzáadás a Start menühöz"
                }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        text: "Mégse"
                        icon.name: "dialog-cancel"
                        onClicked: exe.close()
                    }
                    QQC2.Button {
                        visible: exe.isInstaller
                        text: "Csak futtatás"
                        icon.name: "media-playback-start"
                        onClicked: exe.run(false)
                    }
                    QQC2.Button {
                        highlighted: true
                        text: exe.isInstaller ? "Telepítés" : "Indítás"
                        icon.name: exe.isInstaller ? "download" : "media-playback-start"
                        onClicked: exe.isInstaller ? exe.install() : exe.run(addToMenu.checked)
                    }
                }
                Item { Layout.fillHeight: true }
            }

            // --- Munka közben ----------------------------------------------------
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing * 2
                Item { Layout.fillHeight: true }
                Kirigami.Icon {
                    Layout.alignment: Qt.AlignHCenter
                    source: exe.iconUrl !== "" ? exe.iconUrl : "sloth-os"
                    implicitWidth: Kirigami.Units.iconSizes.huge
                    implicitHeight: Kirigami.Units.iconSizes.huge
                }
                Kirigami.Heading {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    level: 3
                    text: exe.statusText
                }
                QQC2.ProgressBar {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.gridUnit * 2
                    Layout.rightMargin: Kirigami.Units.gridUnit * 2
                    from: 0
                    to: 100
                    value: Math.max(0, exe.progress)
                    indeterminate: exe.progress < 0
                }
                Item { Layout.fillHeight: true }
            }

            // --- Mi kerüljön a Start menübe? ----------------------------------
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    level: 2
                    text: exe.mode === "manage" ? exe.name : "Kész a telepítés!"
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: exe.mode === "manage" ? "Mi legyen a Start menüben?" : "Mi kerüljön a Start menübe?"
                }
                QQC2.ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ListView {
                        model: exe.shortcuts
                        spacing: Kirigami.Units.smallSpacing
                        delegate: QQC2.CheckDelegate {
                            required property var modelData
                            required property int index
                            width: ListView.view.width
                            checked: modelData.checked
                            text: modelData.name
                            icon.source: modelData.iconUrl !== "" ? modelData.iconUrl : "application-x-ms-dos-executable"
                            onClicked: exe.toggleShortcut(index)
                        }
                    }
                }
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    QQC2.Button {
                        highlighted: true
                        text: "Kész"
                        icon.name: "dialog-ok"
                        onClicked: exe.confirmShortcuts()
                    }
                }
            }

            // --- Hiba ------------------------------------------------------------
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing * 2
                Item { Layout.fillHeight: true }
                Kirigami.Icon {
                    Layout.alignment: Qt.AlignHCenter
                    source: "dialog-warning"
                    implicitWidth: Kirigami.Units.iconSizes.huge
                    implicitHeight: Kirigami.Units.iconSizes.huge
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    text: exe.errorText
                }
                QQC2.Button {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Bezárás"
                    onClicked: exe.close()
                }
                Item { Layout.fillHeight: true }
            }

            // --- Fut (az ablak el van rejtve) -------------------------------------
            Item {}
        }
    }
}
