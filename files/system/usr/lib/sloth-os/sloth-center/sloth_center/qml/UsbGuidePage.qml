// A short, safe path to the published Sloth OS USB writing instructions.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    title: L.t("Create installation media")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.Heading {
            level: 2
            text: L.t("Create a Sloth OS USB installer")
        }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: L.t("Download the Sloth OS ISO, then write it to a USB drive with Fedora Media Writer or Rufus. Follow the illustrated guide for the exact steps and boot menu keys.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Warning
            text: L.t("Writing the ISO erases everything on the selected USB drive. Check the drive name and size carefully, and copy any files you want to keep before you start.")
        }

        QQC2.Button {
            text: L.t("Open the installation guide")
            icon.name: "help-contents"
            onClicked: Qt.openUrlExternally("https://sloth-os-linux.github.io/download.html")
        }
        QQC2.Button {
            text: L.t("Download the Sloth OS ISO")
            icon.name: "download"
            onClicked: Qt.openUrlExternally("https://sourceforge.net/projects/sloth-os/files/")
        }
        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.75
            text: L.t("After writing the USB drive, restart the computer and choose the USB device from its boot menu.")
        }
    }
}
