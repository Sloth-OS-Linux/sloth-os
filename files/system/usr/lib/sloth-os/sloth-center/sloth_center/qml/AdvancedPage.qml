// Haladó beállítások: boot menü, kernelparaméterek, rendszercsomagok, környezeti változók,
// bejelentkezéskor induló programok. Minden, amihez máshol terminál kellene
// (rpm-ostree kargs / install / uninstall, ~/.config/environment.d).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Haladó beállítások")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: true
            type: Kirigami.MessageType.Information
            text: L.t("Ezekre a beállításokra általában nincs szükség. Ha valami elromlik, a Frissítések oldalon visszaállhatsz az előző verzióra.")
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: advanced.errorText !== ""
            text: advanced.errorText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: advanced.infoText !== "" && !advanced.busy
            text: advanced.infoText
            actions: [
                Kirigami.Action {
                    text: L.t("Újraindítás most")
                    icon.name: "system-reboot"
                    onTriggered: updates.reboot()
                }
            ]
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: advanced.busy
            QQC2.Label { text: advanced.statusText }
            QQC2.ProgressBar {
                Layout.fillWidth: true
                from: 0; to: 100
                value: Math.max(0, advanced.progress)
                indeterminate: advanced.progress < 0
            }
        }

        // --- Boot menü -------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("Boot menü mutatása induláskor") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("Alapból rejtve van, és csak akkor jelenik meg, ha egy indítás nem sikerült. Kapcsold be, ha a gépen Windows is van, és induláskor választani szeretnél.")
                    }
                }
                QQC2.Switch {
                    checked: advanced.bootMenuVisible
                    onToggled: advanced.setBootMenuVisible(checked)
                }
            }
        }

        // --- Kernelparaméterek -------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Kernelparaméterek") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Hardveres gondok javításához lehet rájuk szükség, ha egy útmutató ezt kéri.")
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: advanced.kernelArgs
                        delegate: Kirigami.Chip {
                            required property var modelData
                            text: modelData.arg
                            checkable: false
                            closable: !modelData.protected && !advanced.busy
                            onRemoved: advanced.removeKernelArg(modelData.arg)
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.TextField {
                        id: kargField
                        Layout.fillWidth: true
                        placeholderText: L.t("Új paraméter, pl. nomodeset")
                        onAccepted: addKarg.clicked()
                    }
                    QQC2.Button {
                        id: addKarg
                        enabled: kargField.text.trim() !== "" && !advanced.busy
                        icon.name: "list-add"
                        text: L.t("Hozzáadás")
                        onClicked: { advanced.addKernelArg(kargField.text); kargField.text = ""; }
                    }
                }
            }
        }

        // --- Rendszercsomagok --------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Rendszercsomagok") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Appokat a Discoverben telepíts. Ide csak olyan rendszerszintű csomagok valók (pl. driverek, parancssori eszközök), amelyek appként nem érhetők el. A frissítések ettől lassabbak lesznek.")
                }
                Repeater {
                    model: advanced.packages
                    delegate: RowLayout {
                        id: pkgRow
                        required property string modelData
                        Layout.fillWidth: true
                        Kirigami.Icon {
                            source: "package-x-generic"
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }
                        QQC2.Label { Layout.fillWidth: true; text: pkgRow.modelData }
                        QQC2.Button {
                            enabled: !advanced.busy
                            icon.name: "edit-delete"
                            text: L.t("Eltávolítás")
                            onClicked: advanced.removePackage(pkgRow.modelData)
                        }
                    }
                }
                QQC2.Label {
                    visible: advanced.packages.length === 0
                    opacity: 0.7
                    text: L.t("Nincs hozzáadott rendszercsomag.")
                }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.TextField {
                        id: pkgField
                        Layout.fillWidth: true
                        placeholderText: L.t("Csomag neve, pl. htop")
                        onAccepted: addPkg.clicked()
                    }
                    QQC2.Button {
                        id: addPkg
                        enabled: pkgField.text.trim() !== "" && !advanced.busy
                        icon.name: "list-add"
                        text: L.t("Telepítés")
                        onClicked: { advanced.addPackage(pkgField.text); pkgField.text = ""; }
                    }
                }
            }
        }

        // --- Környezeti változók (~/.config/environment.d) ------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Környezeti változók") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Beállítások, amelyeket minden program megkap, amit elindítasz (pl. „MANGOHUD=1” minden játékhoz). Csak a te fiókodra vonatkoznak, és a következő bejelentkezéskor lépnek életbe.")
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    type: Kirigami.MessageType.Error
                    visible: environment.errorText !== ""
                    text: environment.errorText
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    type: Kirigami.MessageType.Positive
                    visible: environment.infoText !== ""
                    text: environment.infoText
                    actions: [
                        Kirigami.Action {
                            text: L.t("Kijelentkezés most")
                            icon.name: "system-log-out"
                            onTriggered: environment.logout()
                        }
                    ]
                }
                Repeater {
                    model: environment.variables
                    delegate: RowLayout {
                        id: envRow
                        required property var modelData
                        Layout.fillWidth: true
                        QQC2.Label { text: envRow.modelData.name; font.family: "monospace" }
                        QQC2.Label { text: "=" ; opacity: 0.6 }
                        QQC2.TextField {
                            id: envValue
                            Layout.fillWidth: true
                            font.family: "monospace"
                            text: envRow.modelData.value
                            onAccepted: environment.setVariable(envRow.modelData.name, text)
                        }
                        Kirigami.Icon {
                            visible: envRow.modelData.risky
                            source: "data-warning"
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                            QQC2.ToolTip.visible: riskArea.containsMouse
                            QQC2.ToolTip.text: L.t("Ha ez rosszul van beállítva, a bejelentkezés vagy a programok indítása is elromolhat.")
                            MouseArea { id: riskArea; anchors.fill: parent; hoverEnabled: true }
                        }
                        QQC2.Button {
                            visible: envValue.text !== envRow.modelData.value
                            icon.name: "document-save"
                            text: L.t("Mentés")
                            onClicked: environment.setVariable(envRow.modelData.name, envValue.text)
                        }
                        QQC2.Button {
                            icon.name: "edit-delete"
                            text: L.t("Törlés")
                            onClicked: environment.removeVariable(envRow.modelData.name)
                        }
                    }
                }
                QQC2.Label {
                    visible: environment.variables.length === 0
                    opacity: 0.7
                    text: L.t("Nincs beállított környezeti változó.")
                }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.TextField {
                        id: envName
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 10
                        font.family: "monospace"
                        placeholderText: L.t("Név, pl. MANGOHUD")
                    }
                    QQC2.Label { text: "="; opacity: 0.6 }
                    QQC2.TextField {
                        id: envNewValue
                        Layout.fillWidth: true
                        font.family: "monospace"
                        placeholderText: L.t("Érték, pl. 1")
                        onAccepted: addEnv.clicked()
                    }
                    QQC2.Button {
                        id: addEnv
                        enabled: envName.text.trim() !== ""
                        icon.name: "list-add"
                        text: L.t("Hozzáadás")
                        onClicked: { environment.setVariable(envName.text, envNewValue.text); envName.text = ""; envNewValue.text = ""; }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: environment.otherVariables.length > 0
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("Más programok által beállított változók (itt nem szerkeszthetők):")
                }
                Repeater {
                    model: environment.otherVariables
                    delegate: QQC2.Label {
                        required property var modelData
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        opacity: 0.7
                        font.family: "monospace"
                        text: modelData.name + "=" + modelData.value + "   (" + modelData.file + ")"
                    }
                }
            }
        }

        // --- Bejelentkezéskor induló programok ---------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("Bejelentkezéskor induló programok") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("Programok és szkriptek, amelyek bejelentkezés után maguktól elindulnak. Itt hozzáadhatsz újat, vagy kikapcsolhatod, ami nem kell.")
                    }
                }
                QQC2.Button {
                    icon.name: "system-run"
                    text: L.t("Megnyitás")
                    onClicked: environment.openAutostart()
                }
            }
        }
    }
}
