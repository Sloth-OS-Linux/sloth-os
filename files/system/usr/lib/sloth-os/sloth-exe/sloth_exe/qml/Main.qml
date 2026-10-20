// Az .exe kezelő: mit csináljunk egy programmal? Telepítés / futtatás, folyamatjelzővel.
// A "Wine", "Proton", "prefix" és "Windows" szavak szándékosan nem szerepelnek: a felhasználó
// csak a programot látja (a nevét és a saját ikonját). A szövegek a fordításokból jönnek
// (sloth_exe/translations/<nyelv>.json) a t() függvényen keresztül.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: exe.name

    readonly property var strings: exe.strings
    function t(key, args) {
        let text = root.strings[key];
        if (text === undefined)
            return key;
        if (args)
            for (const k in args)
                text = text.split("{" + k + "}").join(args[k]);
        return text;
    }
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
            currentIndex: ["choose", "working", "pick", "error", "running", "done"].indexOf(exe.state)

            // --- Mit csináljunk? -------------------------------------------------
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing * 2
                Item { Layout.fillHeight: true }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        source: exe.iconUrl !== "" ? exe.iconUrl : "sloth-os"
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                    }
                    ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading {
                            level: 2
                            text: exe.isInstaller ? root.t("title.install", { name: exe.name }) : exe.name
                        }
                        QQC2.Label {
                            Layout.maximumWidth: Kirigami.Units.gridUnit * 18
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: exe.alreadyInstalled ? root.t("choose.already_installed", { name: exe.name })
                                  : exe.nativeReason === "heroic" ? root.t("choose.native_heroic")
                                  : exe.nativeReason === "broken" ? root.t("choose.native_broken", { name: exe.flathubName })
                                  : exe.flathubName !== "" ? root.t("choose.flathub_available", { name: exe.flathubName })
                                  : exe.fileKind === "deb" || exe.fileKind === "rpm" ? root.t("choose.linux_package")
                                  : root.t(exe.isInstaller ? "choose.installer_text" : "choose.program_text")
                        }
                    }
                }
                QQC2.CheckBox {
                    id: addToMenu
                    Layout.alignment: Qt.AlignHCenter
                    visible: !exe.isInstaller
                    text: root.t("choose.add_to_menu")
                }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        text: root.t("button.cancel")
                        icon.name: "dialog-cancel"
                        onClicked: exe.close()
                    }
                    QQC2.Button {
                        visible: exe.isInstaller && !exe.alreadyInstalled
                                 && (exe.fileKind === "windows" || exe.fileKind === "appimage")
                        text: root.t("button.run_only")
                        icon.name: "media-playback-start"
                        onClicked: exe.fileKind === "appimage" ? exe.runOnly() : exe.run(false)
                    }
                    // Más Linux-rendszerhez készült csomag: a Discoveres változat általában jobb választás
                    QQC2.Button {
                        visible: (exe.fileKind === "deb" || exe.fileKind === "rpm") && exe.flathubName === ""
                        text: root.t("button.search_discover")
                        icon.name: "plasmadiscover"
                        onClicked: exe.searchDiscover()
                    }
                    // Már telepítve: újratelepítés ugyanoda, vagy (alapból) megnyitás
                    QQC2.Button {
                        visible: exe.alreadyInstalled
                        text: root.t("button.reinstall")
                        icon.name: "view-refresh"
                        onClicked: exe.install()
                    }
                    QQC2.Button {
                        visible: exe.alreadyInstalled
                        highlighted: true
                        text: root.t("button.open")
                        icon.name: "media-playback-start"
                        onClicked: exe.openExisting()
                    }
                    // A Flathubos változat a javasolt: az a fő gomb, a csomag telepítése marad mellette
                    QQC2.Button {
                        visible: exe.flathubName !== ""
                        highlighted: true
                        text: root.t("button.install_discover")
                        icon.name: "plasmadiscover"
                        onClicked: exe.installFromDiscover()
                    }
                    QQC2.Button {
                        visible: !exe.alreadyInstalled
                        highlighted: exe.flathubName === ""
                        text: root.t(exe.isInstaller ? "button.install" : "button.start")
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
                    text: exe.mode === "manage" ? exe.name : root.t("pick.done_title")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: root.t(exe.mode === "manage" ? "pick.question_manage"
                                 : exe.sure ? "pick.question_install" : "pick.question_unsure")
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
                            icon.source: modelData.iconUrl !== "" ? modelData.iconUrl : "sloth-os"
                            onClicked: exe.toggleShortcut(index)
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    // Ha a felismerés nem találta el: bármelyik .exe kiválasztható
                    QQC2.Button {
                        text: root.t("button.browse")
                        icon.name: "document-open"
                        onClicked: browseDialog.open()
                    }
                    Item { Layout.fillWidth: true }
                    QQC2.Button {
                        highlighted: exe.mode === "manage" || !exe.anyChecked
                        text: root.t("button.done")
                        icon.name: "dialog-ok"
                        onClicked: exe.confirmShortcuts(false)
                    }
                    // Telepítés után: rögtön indítható
                    QQC2.Button {
                        visible: exe.mode !== "manage"
                        enabled: exe.anyChecked
                        highlighted: true
                        text: root.t("button.start")
                        icon.name: "media-playback-start"
                        onClicked: exe.confirmShortcuts(true)
                    }
                }
                FileDialog {
                    id: browseDialog
                    title: root.t("pick.browse_title")
                    currentFolder: exe.browseFolder
                    nameFilters: [root.t("pick.exe_filter") + " (*.exe *.EXE)"]
                    onAccepted: exe.addFile(selectedFile.toString())
                }
            }

            // --- Hiba ------------------------------------------------------------
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing * 2
                Item { Layout.fillHeight: true }
                Kirigami.Icon {
                    Layout.alignment: Qt.AlignHCenter
                    source: exe.errorIcon
                    implicitWidth: Kirigami.Units.iconSizes.huge
                    implicitHeight: Kirigami.Units.iconSizes.huge
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    text: exe.errorText
                }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    QQC2.Button {
                        text: root.t("button.close")
                        onClicked: exe.close()
                    }
                    // Mac-es program: hátha van Linuxos változata
                    QQC2.Button {
                        visible: exe.fileKind === "mac"
                        highlighted: true
                        text: root.t("button.search_discover")
                        icon.name: "plasmadiscover"
                        onClicked: exe.searchDiscover()
                    }
                }
                Item { Layout.fillHeight: true }
            }

            // --- Fut (az ablak el van rejtve) -------------------------------------
            Item {}

            // --- Kész (Linuxos csomag telepítve) --------------------------------
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing * 2
                Item { Layout.fillHeight: true }
                Kirigami.Icon {
                    Layout.alignment: Qt.AlignHCenter
                    source: exe.iconUrl !== "" ? exe.iconUrl : "dialog-ok"
                    implicitWidth: Kirigami.Units.iconSizes.huge
                    implicitHeight: Kirigami.Units.iconSizes.huge
                }
                Kirigami.Heading {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    level: 3
                    text: exe.doneText
                }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    QQC2.Button {
                        text: root.t("button.close")
                        onClicked: exe.close()
                    }
                    QQC2.Button {
                        visible: exe.canStart
                        highlighted: true
                        text: root.t("button.start")
                        icon.name: "media-playback-start"
                        onClicked: exe.startInstalled()
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }
    }
}
