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
    title: L.t("Advanced settings")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: true
            type: Kirigami.MessageType.Information
            text: L.t("You usually don't need these settings. If something breaks, you can go back to the previous version on the Updates page.")
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
                    text: L.t("Restart now")
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
                    Kirigami.Heading { level: 3; text: L.t("Show the boot menu at startup") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("It's hidden by default and only appears if a startup failed. Turn it on if Windows is also on this computer and you want to choose at startup.")
                    }
                }
                QQC2.Switch {
                    checked: advanced.bootMenuVisible
                    onToggled: advanced.setBootMenuVisible(checked)
                }
            }
        }

        // --- Memóriatömörítés (zram) -------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Compressed memory reserve") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("When programs ask for more memory than your computer has, the system keeps rarely used parts compressed in memory, so the computer doesn't stall as easily. With little memory (8 GB or less) and for big games, a larger reserve helps.")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: advanced.zramText
                }
                Repeater {
                    model: [
                        { mode: "default", text: L.t("Default (same as the memory size, up to 8 GB)") },
                        { mode: "more", text: L.t("Larger (1.5 times the memory, up to 24 GB)") },
                        { mode: "off", text: L.t("Off (recommended only with lots of memory)") }
                    ]
                    delegate: QQC2.RadioButton {
                        required property var modelData
                        text: modelData.text
                        checked: advanced.zramMode === modelData.mode
                        onClicked: if (advanced.zramMode !== modelData.mode) advanced.setZramMode(modelData.mode)
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: advanced.zramMode === "custom"
                    opacity: 0.8
                    text: L.t("A custom setting is in effect now. Choosing here will replace it.")
                }
            }
        }

        // --- Windows mellett: a Windows-oldali rendszerindítási segéd ------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: advanced.windowsPresent
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Next to Windows: keep Sloth OS first") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("After a major Windows update, the computer may start Windows directly, without the Sloth OS menu. Sloth OS fixes this the next time it starts; with the helper, Windows itself puts Sloth OS back first every time it starts.")
                }
                QQC2.Button {
                    text: L.t("Place the helper in Windows")
                    icon.name: "windows"
                    onClicked: advanced.placeWindowsHelper()
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: advanced.windowsHelperText !== ""
                    text: advanced.windowsHelperText
                }
            }
        }

        // --- Kernelparaméterek -------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Kernel parameters") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("They may be needed to fix hardware problems, if a guide tells you to.")
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
                        placeholderText: L.t("New parameter, e.g. nomodeset")
                        onAccepted: addKarg.clicked()
                    }
                    QQC2.Button {
                        id: addKarg
                        enabled: kargField.text.trim() !== "" && !advanced.busy
                        icon.name: "list-add"
                        text: L.t("Add")
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
                Kirigami.Heading { level: 3; text: L.t("System packages") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Install apps in Discover. Only system-level packages that aren't available as apps belong here (e.g. drivers, command-line tools). Updates will be slower because of them.")
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
                            text: L.t("Remove")
                            onClicked: advanced.removePackage(pkgRow.modelData)
                        }
                    }
                }
                QQC2.Label {
                    visible: advanced.packages.length === 0
                    opacity: 0.7
                    text: L.t("No system packages added.")
                }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.TextField {
                        id: pkgField
                        Layout.fillWidth: true
                        placeholderText: L.t("Package name, e.g. htop")
                        onAccepted: addPkg.clicked()
                    }
                    QQC2.Button {
                        id: addPkg
                        enabled: pkgField.text.trim() !== "" && !advanced.busy
                        icon.name: "list-add"
                        text: L.t("Install")
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
                Kirigami.Heading { level: 3; text: L.t("Environment variables") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Settings that every program you start receives (e.g. “MANGOHUD=1” for every game). They only apply to your account and take effect at the next sign-in.")
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
                            text: L.t("Sign out now")
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
                            QQC2.ToolTip.text: L.t("If this is set wrongly, signing in or starting programs can break.")
                            MouseArea { id: riskArea; anchors.fill: parent; hoverEnabled: true }
                        }
                        QQC2.Button {
                            visible: envValue.text !== envRow.modelData.value
                            icon.name: "document-save"
                            text: L.t("Save")
                            onClicked: environment.setVariable(envRow.modelData.name, envValue.text)
                        }
                        QQC2.Button {
                            icon.name: "edit-delete"
                            text: L.t("Delete")
                            onClicked: environment.removeVariable(envRow.modelData.name)
                        }
                    }
                }
                QQC2.Label {
                    visible: environment.variables.length === 0
                    opacity: 0.7
                    text: L.t("No environment variables set.")
                }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.TextField {
                        id: envName
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 10
                        font.family: "monospace"
                        placeholderText: L.t("Name, e.g. MANGOHUD")
                    }
                    QQC2.Label { text: "="; opacity: 0.6 }
                    QQC2.TextField {
                        id: envNewValue
                        Layout.fillWidth: true
                        font.family: "monospace"
                        placeholderText: L.t("Value, e.g. 1")
                        onAccepted: addEnv.clicked()
                    }
                    QQC2.Button {
                        id: addEnv
                        enabled: envName.text.trim() !== ""
                        icon.name: "list-add"
                        text: L.t("Add")
                        onClicked: { environment.setVariable(envName.text, envNewValue.text); envName.text = ""; envNewValue.text = ""; }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: environment.otherVariables.length > 0
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("Variables set by other programs (cannot be edited here):")
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
                    Kirigami.Heading { level: 3; text: L.t("Programs started at sign-in") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("Programs and scripts that start on their own after you sign in. Here you can add new ones or turn off what you do not need.")
                    }
                }
                QQC2.Button {
                    icon.name: "system-run"
                    text: L.t("Open")
                    onClicked: environment.openAutostart()
                }
            }
        }
    }
}
