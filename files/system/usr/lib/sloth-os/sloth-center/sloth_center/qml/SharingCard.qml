// Sharing with the shared knowledge: both switches on one card, the same on the Windows programs and the Games page
// (winprograms.sharing / gamesSharing; sloth_common/sharing.py). Two separate yeses, because a Windows program is
// sent only as a fingerprint of its name, a Steam game by its public Steam number. Sloth Welcome asks the same.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.AbstractCard {
    Layout.fillWidth: true
    contentItem: ColumnLayout {
        spacing: Kirigami.Units.largeSpacing
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon {
                source: "network-workgroup"
                implicitWidth: Kirigami.Units.iconSizes.medium
                implicitHeight: Kirigami.Units.iconSizes.medium
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Kirigami.Heading { level: 3; text: L.t("Share experiences"); Layout.fillWidth: true }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("When a Windows program or a Steam game doesn't start right away and Sloth OS finds a setting that works, it can share that setting anonymously, so it starts on the first try on other Sloth OS computers too. Only the setting and your graphics card's manufacturer go with it: never your name, your files or your accounts. You get the settings that worked on other computers either way.")
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                QQC2.Label { text: L.t("Windows programs and games not from Steam"); font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("Only a fingerprint of the program is sent: its name cannot be recovered from it.")
                }
            }
            QQC2.Switch {
                checked: winprograms.sharing
                onToggled: {
                    winprograms.setSharing(checked);
                    checked = Qt.binding(() => winprograms.sharing);
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                QQC2.Label { text: L.t("Steam games"); font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    text: L.t("The game's public Steam number is sent, so the setting can be matched to the game, but never to you.")
                }
            }
            QQC2.Switch {
                checked: winprograms.gamesSharing
                onToggled: {
                    winprograms.setGamesSharing(checked);
                    checked = Qt.binding(() => winprograms.gamesSharing);
                }
            }
        }
    }
}
