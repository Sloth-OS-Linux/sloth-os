// Frissítések és visszaállítás. Csak emberi nyelvű állapot és folyamatjelző,
// terminálkimenet soha. Az adatok a Python oldali `updates` objektumból jönnek.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Updates")

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
                                : updates.needsReboot ? L.t("Restart needed")
                                : updates.updateAvailable ? L.t("A new update is available")
                                : L.t("Your system is up to date")
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: updates.needsReboot && !updates.busy
                                  ? L.tf("After a restart, this starts: {version}", { version: updates.pendingVersion })
                                  : updates.updateAvailable && !updates.busy
                                  ? L.tf("Available version: {version}", { version: updates.availableVersion })
                                  : L.tf("Current version: {version}", { version: updates.currentVersion || "–" })
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
                        text: L.t("Check for updates")
                        onClicked: updates.checkForUpdates()
                    }
                    QQC2.Button {
                        visible: !updates.busy && !updates.needsReboot && updates.updateAvailable
                        icon.name: "download"
                        text: L.t("Install update")
                        onClicked: updates.installUpdate()
                    }
                    QQC2.Button {
                        visible: !updates.busy && updates.needsReboot
                        icon.name: "system-reboot"
                        text: L.t("Restart now")
                        onClicked: updates.reboot()
                    }
                    QQC2.Button {
                        visible: updates.busy && (updates.mode === "check" || updates.mode === "upgrade")
                        icon.name: "dialog-cancel"
                        text: L.t("Cancel")
                        onClicked: updates.cancel()
                    }
                }

                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    visible: !updates.busy
                    text: L.t("The update is prepared in the background; you can keep working in the meantime. The new version takes effect at the next restart.")
                }
            }
        }

        // --- Appok: a Discover és az automatikus app-frissítés ------------------------------------
        // A rendszert ez az oldal frissíti, az appokat (Flatpak) a háttérben egy napi frissítő, kézzel a
        // Discover; a Discover a rendszerfrissítést nem mutatja (nincs két külön rendszerfrissítés)
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: "plasmadiscover"
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: Kirigami.Units.iconSizes.medium
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 3; text: L.t("Apps"); Layout.fillWidth: true }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: L.t("Apps (the ones you installed in Welcome or Discover) update themselves once a day, unless you're on a mobile or other metered connection. Windows programs and game stores (such as Steam or Battle.net) update themselves.")
                    }
                }
                QQC2.Button {
                    text: L.t("Open in Discover")
                    icon.name: "plasmadiscover"
                    onClicked: updates.openDiscover()
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
                    Kirigami.Heading { level: 3; text: L.t("Keep the current version") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("If everything works well now, you can mark this version. Later updates won't delete it, so if a newer version has problems, you can always go back to this one.")
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
                    text: L.t("Roll back to the previous version")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: updates.rollbackVersion !== ""
                          ? L.tf("If something hasn't worked right since the last update, you can go back to the previous version ({version}). Your files and settings are kept.", { version: updates.rollbackVersion })
                          : L.t("There's no earlier version to go back to yet.")
                }
                QQC2.Button {
                    enabled: updates.canRollback
                    icon.name: "edit-undo"
                    text: L.t("Back to the previous version")
                    onClicked: confirmRollback.open()
                }
            }
        }

        // --- Az összes verzió a gépen ----------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: updates.versions.length > 1
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Versions on this computer") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("These system versions are on the computer now. You can start any of them at the next restart, without downloading anything. Updates do not delete the kept ones.")
                }
                Repeater {
                    model: updates.versions
                    delegate: RowLayout {
                        id: verRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: verRow.modelData.booted ? "emblem-default" : "system-software-update"
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: verRow.modelData.name }
                            QQC2.Label {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                opacity: 0.7
                                font: Kirigami.Theme.smallFont
                                text: [verRow.modelData.booted ? L.t("running now") : "",
                                       verRow.modelData.next ? L.t("starts next time") : "",
                                       verRow.modelData.pinned ? L.t("kept") : ""].filter(x => x).join(" · ")
                            }
                        }
                        QQC2.Button {
                            visible: !verRow.modelData.next
                            enabled: !updates.busy
                            icon.name: "system-reboot"
                            text: L.t("Start this one next time")
                            onClicked: updates.bootVersion(verRow.modelData.index)
                        }
                        QQC2.CheckBox {
                            text: L.t("Keep")
                            checked: verRow.modelData.pinned
                            enabled: !updates.busy
                            onToggled: updates.setVersionPinned(verRow.modelData.index, checked)
                        }
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirmRollback
        title: L.t("Go back to the previous version?")
        subtitle: L.tf("After a restart, the previous version ({version}) starts. Your files and settings are kept, and you can update again later.", { version: updates.rollbackVersion })
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Go back")
                icon.name: "edit-undo"
                onTriggered: { confirmRollback.close(); updates.rollback(); }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirmRollback.close()
            }
        ]
    }
}
