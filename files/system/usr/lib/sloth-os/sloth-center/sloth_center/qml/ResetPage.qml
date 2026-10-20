// A gép alaphelyzetbe állítása: „Fájljaim megtartásával” vagy „Mindent töröl” (reset.py).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Alaphelyzetbe állítás")

    // "" (választás), "keep" vagy "all" (a választott mód összefoglalója)
    property string choice: ""

    readonly property var lists: ({
        keep: {
            title: L.t("Fájljaim megtartásával"),
            stays: [
                L.t("A fájljaid (Dokumentumok, Képek, Letöltések és a többi)"),
                L.t("Az appok adatai és a játékok: ha újratelepíted őket, minden ott lesz"),
                L.t("A fiókok, a Wi-Fi jelszavak és a mentett állapotok")
            ],
            goes: [
                L.t("A telepített appok (újraindítás után az Üdvözlőben újra kiválaszthatod őket)"),
                L.t("Az asztal beállításai (téma, tálca, háttér). A régiek a „Régi beállítások” mappába kerülnek."),
                L.t("A rendszerbeállítások, a kézzel hozzáadott rendszercsomagok és kernelparaméterek")
            ]
        },
        all: {
            title: L.t("Mindent töröl"),
            stays: [
                L.t("A nyelv, az időzóna, a billentyűzet és a lemeztitkosítás")
            ],
            goes: [
                L.t("Minden fiók, és bennük minden fájl"),
                L.t("Az összes app, beállítás, Wi-Fi jelszó és mentett állapot")
            ]
        }
    })

    readonly property string accountProblem: {
        if (choice !== "all")
            return ""
        if (usernameField.text === "")
            return L.t("Adj meg egy felhasználónevet.")
        const bad = reset.checkAccount(usernameField.text)
        if (bad !== "")
            return bad
        if (passwordField.text === "")
            return L.t("Adj meg egy jelszót.")
        if (passwordField.text !== password2Field.text)
            return L.t("A két jelszó nem egyezik.")
        return ""
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: reset.errorText !== ""
            type: Kirigami.MessageType.Error
            text: reset.errorText
        }

        // --- Előkészítés folyamatban --------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: reset.busy
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Az alaphelyzetbe állítás előkészítése") }
                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: reset.statusText }
                QQC2.ProgressBar { Layout.fillWidth: true; indeterminate: true }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Közben nyugodtan dolgozhatsz tovább.")
                }
            }
        }

        // --- Elő van készítve: újraindításra vár ---------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: !reset.busy && reset.pendingMode !== ""
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: "system-reboot"
                        implicitWidth: Kirigami.Units.iconSizes.large
                        implicitHeight: Kirigami.Units.iconSizes.large
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading { level: 3; text: L.t("Minden készen áll") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: L.t("Az alaphelyzetbe állítás a következő újraindításkor történik meg, bejelentkezés előtt. Néhány percig tart, közben a gép egyszer magától újraindul.")
                        }
                    }
                }
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    QQC2.Button {
                        icon.name: "dialog-cancel"
                        text: L.t("Mégse, nem kérem")
                        onClicked: reset.cancel()
                    }
                    QQC2.Button {
                        icon.name: "system-reboot"
                        text: L.t("Újraindítás most")
                        onClicked: reset.restartNow()
                    }
                }
            }
        }

        // --- Választás --------------------------------------------------------------------------
        Repeater {
            model: [
                { mode: "keep", icon: "edit-undo", title: L.t("Fájljaim megtartásával"),
                  text: L.t("A rendszer és az appok visszaállnak a gyári állapotra, a fájljaid megmaradnak. Akkor hasznos, ha valami nem működik jól.") },
                { mode: "all", icon: "edit-delete", title: L.t("Mindent töröl"),
                  text: L.t("Minden fiók és fájl törlődik, a gép olyan lesz, mint frissen telepítve. Eladás vagy továbbadás előtt hasznos.") }
            ]
            delegate: Kirigami.AbstractCard {
                id: option
                required property var modelData
                Layout.fillWidth: true
                visible: !reset.busy && reset.pendingMode === "" && page.choice === ""
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: option.modelData.icon
                        implicitWidth: Kirigami.Units.iconSizes.large
                        implicitHeight: Kirigami.Units.iconSizes.large
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading { level: 3; text: option.modelData.title }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: option.modelData.text
                        }
                    }
                    QQC2.Button {
                        text: L.t("Kezdés…")
                        onClicked: page.choice = option.modelData.mode
                    }
                }
            }
        }

        // --- A választott mód: mi marad, mi törlődik ------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: !reset.busy && reset.pendingMode === "" && page.choice !== ""
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 2; text: page.choice ? page.lists[page.choice].title : "" }

                QQC2.Label { text: L.t("Ami megmarad:"); font.bold: true }
                Repeater {
                    model: page.choice ? page.lists[page.choice].stays : []
                    delegate: RowLayout {
                        id: stay
                        required property string modelData
                        Layout.fillWidth: true
                        Kirigami.Icon {
                            source: "checkmark"
                            isMask: true
                            color: Kirigami.Theme.positiveTextColor
                            Layout.alignment: Qt.AlignTop
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                        }
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: stay.modelData }
                    }
                }

                QQC2.Label { text: L.t("Ami törlődik:"); font.bold: true }
                Repeater {
                    model: page.choice ? page.lists[page.choice].goes : []
                    delegate: RowLayout {
                        id: goes
                        required property string modelData
                        Layout.fillWidth: true
                        Kirigami.Icon {
                            source: "edit-delete"
                            Layout.alignment: Qt.AlignTop
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                        }
                        QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: goes.modelData }
                    }
                }

                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Előtte letöltjük a legújabb Sloth OS verziót, így a gép azzal indul újra.")
                }

                // „Mindent töröl”: az új fiók (újraindítás után ezzel lehet belépni)
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: page.choice === "all"
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("Az új fiók") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("Újraindítás után ezzel lehet bejelentkezni. Ha a gépet továbbadod, az új tulajdonos később a saját fiókját is létrehozhatja.")
                    }
                    QQC2.TextField {
                        id: fullnameField
                        Layout.fillWidth: true
                        placeholderText: L.t("Teljes név")
                    }
                    QQC2.TextField {
                        id: usernameField
                        Layout.fillWidth: true
                        placeholderText: L.t("Felhasználónév (pl. anna)")
                    }
                    QQC2.TextField {
                        id: passwordField
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: L.t("Jelszó")
                    }
                    QQC2.TextField {
                        id: password2Field
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: L.t("Jelszó még egyszer")
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        visible: page.accountProblem !== "" && (usernameField.text !== "" || passwordField.text !== "")
                        color: Kirigami.Theme.negativeTextColor
                        text: page.accountProblem
                    }
                }

                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    QQC2.Button {
                        icon.name: "go-previous"
                        text: L.t("Vissza")
                        onClicked: page.choice = ""
                    }
                    QQC2.Button {
                        icon.name: "edit-undo"
                        enabled: page.accountProblem === ""
                        text: L.t("Alaphelyzetbe állítás…")
                        onClicked: confirm.open()
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirm
        title: L.t("Biztosan alaphelyzetbe állítod a gépet?")
        subtitle: page.choice === "all"
                  ? L.t("Minden fiók és fájl véglegesen törlődik. Ezt nem lehet visszavonni.")
                  : L.t("A telepített appok és a beállítások törlődnek, a fájljaid megmaradnak.")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: page.choice === "all" ? L.t("Mindent töröl") : L.t("Alaphelyzetbe állítás")
                icon.name: page.choice === "all" ? "edit-delete" : "edit-undo"
                onTriggered: {
                    confirm.close()
                    reset.start(page.choice, fullnameField.text, usernameField.text, passwordField.text)
                    passwordField.text = ""
                    password2Field.text = ""
                    page.choice = ""
                }
            },
            Kirigami.Action {
                text: L.t("Mégse")
                icon.name: "dialog-cancel"
                onTriggered: confirm.close()
            }
        ]
    }
}
