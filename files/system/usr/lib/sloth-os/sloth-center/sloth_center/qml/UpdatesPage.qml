// Frissítések és visszaállítás. Csak emberi nyelvű állapot és folyamatjelző,
// terminálkimenet soha. Az adatok a Python oldali `updates` objektumból jönnek.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Frissítések")

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
                                : updates.needsReboot ? L.t("Újraindítás szükséges")
                                : updates.updateAvailable ? L.t("Új frissítés érhető el")
                                : L.t("A rendszered naprakész")
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: updates.needsReboot && !updates.busy
                                  ? L.tf("Újraindítás után ez indul: {version}", { version: updates.pendingVersion })
                                  : updates.updateAvailable && !updates.busy
                                  ? L.tf("Elérhető verzió: {version}", { version: updates.availableVersion })
                                  : L.tf("Jelenlegi verzió: {version}", { version: updates.currentVersion || "–" })
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
                        text: L.t("Frissítések keresése")
                        onClicked: updates.checkForUpdates()
                    }
                    QQC2.Button {
                        visible: !updates.busy && !updates.needsReboot && updates.updateAvailable
                        icon.name: "download"
                        text: L.t("Frissítés telepítése")
                        onClicked: updates.installUpdate()
                    }
                    QQC2.Button {
                        visible: !updates.busy && updates.needsReboot
                        icon.name: "system-reboot"
                        text: L.t("Újraindítás most")
                        onClicked: updates.reboot()
                    }
                    QQC2.Button {
                        visible: updates.busy && (updates.mode === "check" || updates.mode === "upgrade")
                        icon.name: "dialog-cancel"
                        text: L.t("Mégse")
                        onClicked: updates.cancel()
                    }
                }

                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    visible: !updates.busy
                    text: L.t("A frissítés a háttérben készül el, közben nyugodtan dolgozhatsz tovább. Az új verzió a következő újraindításkor lép életbe.")
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
                    Kirigami.Heading { level: 3; text: L.t("Appok"); Layout.fillWidth: true }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: L.t("Az appok (amiket az Üdvözlőben vagy a Discoverben telepítettél) maguktól frissülnek, naponta egyszer, ha nem mobilnetes vagy más mért kapcsolaton vagy. A Windows-programok és a játékboltok (például a Steam vagy a Battle.net) saját magukat frissítik.")
                    }
                }
                QQC2.Button {
                    text: L.t("Megnyitás a Discoverben")
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
                    Kirigami.Heading { level: 3; text: L.t("A mostani verzió megtartása") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("Ha most minden jól működik, megjelölheted ezt a verziót. A későbbi frissítések nem törlik, így ha egy újabb verzióval gond lenne, erre biztosan vissza lehet állni.")
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
                    text: L.t("Visszaállítás az előző verzióra")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: updates.rollbackVersion !== ""
                          ? L.tf("Ha a legutóbbi frissítés óta valami nem működik jól, visszatérhetsz az előző verzióhoz ({version}). A fájljaid és beállításaid megmaradnak.", { version: updates.rollbackVersion })
                          : L.t("Még nincs korábbi verzió, amire vissza lehetne állni.")
                }
                QQC2.Button {
                    enabled: updates.canRollback
                    icon.name: "edit-undo"
                    text: L.t("Vissza az előző verzióra")
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
                Kirigami.Heading { level: 3; text: L.t("Verziók a gépen") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Ezek a rendszerverziók vannak most a gépen. Bármelyiket elindíthatod a következő újraindításkor, letöltés nélkül. A megtartottakat a frissítések nem törlik.")
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
                                text: [verRow.modelData.booted ? L.t("most ez fut") : "",
                                       verRow.modelData.next ? L.t("ez indul legközelebb") : "",
                                       verRow.modelData.pinned ? L.t("megtartva") : ""].filter(x => x).join(" · ")
                            }
                        }
                        QQC2.Button {
                            visible: !verRow.modelData.next
                            enabled: !updates.busy
                            icon.name: "system-reboot"
                            text: L.t("Ezt indítsd legközelebb")
                            onClicked: updates.bootVersion(verRow.modelData.index)
                        }
                        QQC2.CheckBox {
                            text: L.t("Megtartás")
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
        title: L.t("Visszaállás az előző verzióra?")
        subtitle: L.tf("Újraindítás után az előző verzió ({version}) indul. A fájljaid és beállításaid megmaradnak, és később újra frissíthetsz.", { version: updates.rollbackVersion })
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Visszaállás")
                icon.name: "edit-undo"
                onTriggered: { confirmRollback.close(); updates.rollback(); }
            },
            Kirigami.Action {
                text: L.t("Mégse")
                icon.name: "dialog-cancel"
                onTriggered: confirmRollback.close()
            }
        ]
    }
}
