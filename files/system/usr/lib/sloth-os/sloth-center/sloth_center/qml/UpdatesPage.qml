// Frissítések és visszaállítás. Csak emberi nyelvű állapot és folyamatjelző,
// terminálkimenet soha. Az adatok a Python oldali `updates` objektumból jönnek.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: "Frissítések"

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: updates.unavailableText !== ""
            text: updates.unavailableText
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: updates.errorText !== ""
            text: updates.errorText
            showCloseButton: true
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: updates.infoText !== "" && !updates.busy
            text: updates.infoText
        }

        // --- Fő állapot ------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

                RowLayout {
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                        source: updates.busy ? "system-software-update"
                              : updates.needsReboot ? "system-reboot"
                              : updates.updateAvailable ? "update-high"
                              : "security-high"
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            level: 2
                            text: updates.busy ? updates.statusText
                                : updates.needsReboot ? "Újraindítás szükséges"
                                : updates.updateAvailable ? "Új frissítés érhető el"
                                : "A rendszered naprakész"
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: updates.needsReboot && !updates.busy
                                  ? "Újraindítás után ez indul: " + updates.pendingVersion
                                  : updates.updateAvailable && !updates.busy
                                  ? "Elérhető verzió: " + updates.availableVersion
                                  : "Jelenlegi verzió: " + (updates.currentVersion || "–")
                        }
                    }
                }

                // Folyamatjelző: százalék, ha tudjuk; különben mozgó csík
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: updates.busy
                    spacing: Kirigami.Units.smallSpacing
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: Math.max(0, updates.progress)
                        indeterminate: updates.progress < 0
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        QQC2.Label {
                            Layout.fillWidth: true
                            opacity: 0.7
                            text: updates.detailText
                        }
                        QQC2.Label {
                            visible: updates.progress >= 0
                            opacity: 0.7
                            text: updates.progress + "%"
                        }
                    }
                }

                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        visible: !updates.busy && !updates.needsReboot && !updates.updateAvailable
                        enabled: updates.unavailableText === ""
                        icon.name: "view-refresh"
                        text: "Frissítések keresése"
                        onClicked: updates.checkForUpdates()
                    }
                    QQC2.Button {
                        visible: !updates.busy && !updates.needsReboot && updates.updateAvailable
                        icon.name: "download"
                        text: "Frissítés telepítése"
                        onClicked: updates.installUpdate()
                    }
                    QQC2.Button {
                        visible: !updates.busy && updates.needsReboot
                        icon.name: "system-reboot"
                        text: "Újraindítás most"
                        onClicked: updates.reboot()
                    }
                    QQC2.Button {
                        visible: updates.busy && (updates.mode === "check" || updates.mode === "upgrade")
                        icon.name: "dialog-cancel"
                        text: "Mégse"
                        onClicked: updates.cancel()
                    }
                }

                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    visible: !updates.busy
                    text: "A frissítés a háttérben készül el, közben nyugodtan dolgozhatsz tovább. " +
                          "Az új verzió a következő újraindításkor lép életbe."
                }
            }
        }

        // --- Verzió megtartása ---------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: "A mostani verzió megtartása" }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: "Ha most minden jól működik, megjelölheted ezt a verziót. A későbbi frissítések nem törlik, így ha egy újabb verzióval gond lenne, erre biztosan vissza lehet állni."
                    }
                }
                QQC2.Switch {
                    checked: updates.pinned
                    enabled: updates.canPin
                    onToggled: updates.setPinned(checked)
                }
            }
        }

        // --- Visszaállítás -----------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading {
                    level: 3
                    text: "Visszaállítás az előző verzióra"
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: updates.rollbackVersion !== ""
                          ? "Ha a legutóbbi frissítés óta valami nem működik jól, visszatérhetsz az előző verzióhoz (" +
                            updates.rollbackVersion + "). A fájljaid és beállításaid megmaradnak."
                          : "Még nincs korábbi verzió, amire vissza lehetne állni."
                }
                QQC2.Button {
                    enabled: updates.canRollback
                    icon.name: "edit-undo"
                    text: "Vissza az előző verzióra"
                    onClicked: confirmRollback.open()
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirmRollback
        title: "Visszaállás az előző verzióra?"
        subtitle: "Újraindítás után az előző verzió (" + updates.rollbackVersion + ") indul. " +
                  "A fájljaid és beállításaid megmaradnak, és később újra frissíthetsz."
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: "Visszaállás"
                icon.name: "edit-undo"
                onTriggered: { confirmRollback.close(); updates.rollback(); }
            },
            Kirigami.Action {
                text: "Mégse"
                icon.name: "dialog-cancel"
                onTriggered: confirmRollback.close()
            }
        ]
    }
}
