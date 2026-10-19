// Fejlesztői pult: a Sloth OS fejlesztése terminál nélkül (repó, build, aláíró kulcs, kipróbálás).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Fejlesztői pult")

    actions: [
        Kirigami.Action {
            text: L.t("Frissítés")
            icon.name: "view-refresh"
            enabled: devpanel.connected
            onTriggered: devpanel.refresh()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: devpanel.errorText !== ""
            text: devpanel.errorText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Information
            visible: devpanel.message !== ""
            text: devpanel.message
        }
        QQC2.ProgressBar {
            Layout.fillWidth: true
            visible: devpanel.busy
            indeterminate: true
        }

        // --- Kapcsolat ------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Kapcsolat a GitHubbal") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: devpanel.connected
                          ? L.tf("Kapcsolódva: {repo}", { repo: devpanel.repo })
                          : L.t("Add meg a repót és egy GitHub-tokent. A tokent a gomb a GitHubon hozza létre, a szükséges jogokkal (repó, build, csomagok olvasása); onnan másold ide. A jelszótárolóban marad, ebből a gépből bármikor törölhető.")
                }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.TextField {
                        id: repoField
                        Layout.fillWidth: true
                        text: devpanel.repo
                        placeholderText: "bathorizsolt/sloth-os"
                    }
                    QQC2.TextField {
                        id: tokenField
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: devpanel.connected ? L.t("Token (csak ha cserélnéd)") : L.t("Token")
                    }
                }
                RowLayout {
                    QQC2.Button {
                        text: L.t("Token létrehozása a GitHubon")
                        icon.name: "internet-services"
                        onClicked: devpanel.createToken()
                    }
                    QQC2.Button {
                        highlighted: !devpanel.connected
                        enabled: !devpanel.busy
                        text: L.t("Kapcsolódás")
                        icon.name: "network-connect"
                        onClicked: { devpanel.connectRepo(repoField.text, tokenField.text); tokenField.text = ""; }
                    }
                    QQC2.Button {
                        visible: devpanel.connected
                        text: L.t("Token törlése")
                        icon.name: "edit-delete"
                        onClicked: devpanel.disconnect()
                    }
                }
            }
        }

        // --- Buildek ----------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: devpanel.connected
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                RowLayout {
                    Layout.fillWidth: true
                    Kirigami.Heading { level: 3; text: L.t("Buildek"); Layout.fillWidth: true }
                    QQC2.Label {
                        visible: devpanel.minutes >= 0
                        opacity: 0.7
                        text: L.tf("Ebben a hónapban: {minutes} perc", { minutes: devpanel.minutes })
                    }
                }
                RowLayout {
                    QQC2.Button {
                        enabled: !devpanel.busy
                        text: L.t("Image build indítása")
                        icon.name: "run-build"
                        onClicked: devpanel.startBuild("image")
                    }
                    QQC2.Button {
                        enabled: !devpanel.busy
                        text: L.t("ISO build indítása")
                        icon.name: "media-optical"
                        onClicked: devpanel.startBuild("iso")
                    }
                }
                Repeater {
                    model: devpanel.runs
                    delegate: RowLayout {
                        id: runRow
                        required property var modelData
                        Layout.fillWidth: true
                        Kirigami.Icon {
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                            source: runRow.modelData.state === "ok" ? "emblem-success"
                                  : runRow.modelData.state === "running" ? "chronometer"
                                  : runRow.modelData.state === "cancelled" ? "emblem-pause" : "emblem-error"
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: runRow.modelData.when + " · " + runRow.modelData.name + " · " + runRow.modelData.title
                        }
                        QQC2.Button {
                            visible: runRow.modelData.state === "ok" && runRow.modelData.name === "bluebuild"
                            enabled: !devpanel.busy
                            text: L.t("Átállás erre")
                            icon.name: "go-jump"
                            QQC2.ToolTip.visible: hovered
                            QQC2.ToolTip.text: L.t("Ez a gép a következő újraindításkor erről a buildről indul. A mostani változat a boot menüben marad.")
                            onClicked: devpanel.switchTo(devpanel.tagFor(runRow.modelData.sha))
                        }
                        QQC2.ToolButton {
                            icon.name: "internet-services"
                            text: L.t("Megnyitás a GitHubon")
                            display: QQC2.AbstractButton.IconOnly
                            QQC2.ToolTip.visible: hovered
                            QQC2.ToolTip.text: text
                            onClicked: devpanel.openUrl(runRow.modelData.url)
                        }
                    }
                }
            }
        }

        // --- Aláíró kulcs ------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: devpanel.connected
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Aláíró kulcs") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: !devpanel.secretKnown ? ""
                          : devpanel.hasSecret ? L.t("Be van állítva: a buildek aláírva készülnek, a gépek ellenőrzik a frissítések aláírását.")
                          : L.t("Még nincs beállítva: a buildek aláírás nélkül nem készülnek el.")
                }
                QQC2.Button {
                    enabled: !devpanel.busy
                    text: devpanel.hasSecret ? L.t("Új kulcspár…") : L.t("Kulcspár létrehozása")
                    icon.name: "document-encrypt"
                    onClicked: devpanel.hasSecret ? keyConfirm.open() : devpanel.createSigningKey()
                }
            }
        }

        // --- Kipróbálás --------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: devpanel.connected
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 3; text: L.t("Kipróbálás") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.tf("Ez a gép most ezt futtatja: {image}", { image: devpanel.currentImage !== "" ? devpanel.currentImage : "?" })
                }
                RowLayout {
                    QQC2.Button {
                        visible: devpanel.privateRepo
                        enabled: !devpanel.busy
                        text: L.t("Bejelentkezés a csomagtárolóba")
                        icon.name: "unlock"
                        QQC2.ToolTip.visible: hovered
                        QQC2.ToolTip.text: L.t("Privát repónál kell: enélkül a gép nem tölti le a frissítéseket és a buildeket.")
                        onClicked: devpanel.registryLogin()
                    }
                    QQC2.Button {
                        enabled: !devpanel.busy
                        text: L.t("Vissza a legfrissebbre")
                        icon.name: "go-home"
                        onClicked: devpanel.switchTo("latest")
                    }
                    QQC2.Button {
                        text: L.t("Virtuális gép")
                        icon.name: "computer"
                        onClicked: devpanel.openBoxes()
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: keyConfirm
        title: L.t("Új aláíró kulcs?")
        subtitle: L.t("A már telepített gépek a régi kulccsal aláírt frissítéseket fogadják el. Új kulcs után a frissítésük addig áll, amíg az új nyilvános kulcs (cosign.pub) nem kerül rájuk egy olyan frissítéssel, amit még a régi kulcs írt alá. Csak akkor cseréld, ha a régi kulcs elveszett vagy kiszivárgott.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Új kulcspár")
                icon.name: "document-encrypt"
                onTriggered: { devpanel.createSigningKey(); keyConfirm.close(); }
            },
            Kirigami.Action {
                text: L.t("Mégse")
                icon.name: "dialog-cancel"
                onTriggered: keyConfirm.close()
            }
        ]
    }
}
