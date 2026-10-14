// Fiók és biztonság: mihez kérjen jelszót a rendszer (témakörönként), automatikus bejelentkezés, sudo.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Fiók és biztonság")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: accounts.errorText !== ""
            text: accounts.errorText
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: accounts.infoText !== ""
            text: accounts.infoText
        }

        // --- A fiók -------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: accounts.isAdmin ? "user-admin" : "user-identity"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 3; text: accounts.userName }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: accounts.isAdmin ? L.t("Rendszergazda vagy: a gép beállításait is módosíthatod.")
                                               : L.t("Normál fiók: a gép beállításaihoz egy rendszergazda jelszava kell.")
                    }
                }
                QQC2.Button {
                    icon.name: "preferences-system-users"
                    text: L.t("Felhasználók kezelése")
                    onClicked: accounts.openUsers()
                }
            }
        }

        // --- Mihez kérjen jelszót -------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            enabled: accounts.isAdmin
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Mihez kérjen jelszót a rendszer?") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Ha egy beállításhoz nem kell jelszó, az a te fiókodból kérdés nélkül lefut. Ez kényelmes, de ha valaki más ül a gépedhez, ő is megteheti. A lemezekhez, a felhasználókhoz és a rendszerindításhoz ajánlott megtartani a jelszót.")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: !accounts.isAdmin
                    wrapMode: Text.Wrap
                    color: Kirigami.Theme.neutralTextColor
                    text: L.t("Ezt csak rendszergazda fiókkal lehet bekapcsolni.")
                }
                QQC2.ButtonGroup { id: presets }
                QQC2.RadioButton {
                    QQC2.ButtonGroup.group: presets
                    text: L.t("Mindenhez kérjen jelszót (a legbiztonságosabb)")
                    checked: accounts.preset === "all"
                    onClicked: accounts.applyPreset("all")
                }
                QQC2.RadioButton {
                    QQC2.ButtonGroup.group: presets
                    text: L.t("Csak a kockázatos dolgokhoz kérjen jelszót (lemezek, felhasználók, rendszerindítás)")
                    checked: accounts.preset === "recommended"
                    onClicked: accounts.applyPreset("recommended")
                }
                QQC2.RadioButton {
                    id: customPreset
                    QQC2.ButtonGroup.group: presets
                    text: L.t("Egyénileg, témakörönként")
                    checked: accounts.preset === "custom"
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.gridUnit
                    visible: customPreset.checked
                    spacing: Kirigami.Units.largeSpacing
                    Repeater {
                        model: accounts.topics
                        delegate: RowLayout {
                            id: topicRow
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: topicRow.modelData.name }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    opacity: 0.7
                                    font: Kirigami.Theme.smallFont
                                    text: topicRow.modelData.description
                                }
                            }
                            Kirigami.Icon {
                                visible: topicRow.modelData.risky && !topicRow.modelData.passwordNeeded
                                source: "data-warning"
                                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                                implicitHeight: Kirigami.Units.iconSizes.smallMedium
                            }
                            QQC2.Switch {
                                text: L.t("Jelszó kell")
                                checked: topicRow.modelData.passwordNeeded
                                onToggled: accounts.setPasswordNeeded(topicRow.modelData.id, checked)
                            }
                        }
                    }
                }
            }
        }

        // --- Bejelentkezés és terminál ------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Kirigami.Heading { level: 3; text: L.t("Automatikus bejelentkezés") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: L.t("Bekapcsolás után a gép jelszó nélkül, egyből a te asztaloddal indul. A mentett jelszavak (pl. Wi-Fi, böngésző) tárolója ilyenkor az első használatkor kéri a jelszavad.")
                        }
                    }
                    QQC2.Switch {
                        checked: accounts.autologin
                        onToggled: accounts.setAutologin(checked)
                    }
                }
                Kirigami.Separator { Layout.fillWidth: true }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    enabled: accounts.isAdmin
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Kirigami.Heading { level: 3; text: L.t("Jelszó a terminálban (sudo)") }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: L.t("Haladóknak: kapcsold ki, ha nem szeretnéd, hogy a terminálban a „sudo” parancs jelszót kérjen.")
                        }
                    }
                    QQC2.Switch {
                        text: L.t("Jelszó kell")
                        checked: !accounts.sudoWithoutPassword
                        onToggled: accounts.setSudoWithoutPassword(!checked)
                    }
                }
            }
        }
    }
}
