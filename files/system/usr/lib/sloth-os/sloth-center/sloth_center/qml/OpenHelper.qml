// The "I can't open this file" helper's window (open_helper.py): the app that opens the file, installed with one
// click; or Discover's search for a file type it has no suggestion for.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: helper.fileName
    width: Kirigami.Units.gridUnit * 30
    height: Kirigami.Units.gridUnit * 16
    minimumWidth: Kirigami.Units.gridUnit * 22
    minimumHeight: Kirigami.Units.gridUnit * 13
    visible: true
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    // not closed halfway through an install (the window closes by itself once the file opens)
    onClosing: close => close.accepted = helper.state !== "installing"

    pageStack.initialPage: Kirigami.Page {
        padding: Kirigami.Units.gridUnit

        ColumnLayout {
            anchors.fill: parent
            spacing: Kirigami.Units.largeSpacing

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: helper.appIcon
                    Layout.preferredWidth: Kirigami.Units.iconSizes.huge
                    Layout.preferredHeight: Kirigami.Units.iconSizes.huge
                    Layout.alignment: Qt.AlignTop
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        level: 2
                        wrapMode: Text.Wrap
                        text: L.t("No app on this computer opens “%1” yet.").arg(helper.fileName)
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        visible: helper.state === "offer" || helper.state === "installing"
                        text: L.t("%1 opens it: %2. It is free, and it installs in a minute or two.").arg(helper.appName).arg(helper.appWhat)
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        visible: helper.state === "unknown"
                        text: L.t("Sloth OS doesn't know an app for this kind of file (%1). Discover can look for one.").arg(helper.typeName)
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        visible: helper.state === "failed"
                        color: Kirigami.Theme.negativeTextColor
                        text: L.t("The installation did not succeed. Check the internet connection and try again.")
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                visible: helper.state === "installing"
                spacing: Kirigami.Units.smallSpacing
                QQC2.Label {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    text: helper.status !== "" ? helper.status : L.t("Getting ready…")
                }
                QQC2.ProgressBar {
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    value: Math.max(0, helper.percent)
                    indeterminate: helper.percent < 0
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                Item { Layout.fillWidth: true }
                QQC2.Button {
                    visible: helper.state === "unknown"
                    text: L.t("Search in Discover")
                    icon.name: "plasmadiscover"
                    onClicked: helper.searchDiscover()
                }
                QQC2.Button {
                    visible: helper.state === "offer" || helper.state === "failed"
                    text: helper.state === "failed" ? L.t("Try again") : L.t("Install %1 and open the file").arg(helper.appName)
                    icon.name: "download"
                    highlighted: true
                    onClicked: helper.install()
                }
                QQC2.Button {
                    text: L.t("Cancel")
                    enabled: helper.state !== "installing"
                    onClicked: root.close()
                }
            }
        }
    }
}
