// Wi-Fi and network: Wi-Fi on and off, the networks around (connect, disconnect, forget), the wired connection
// (network.py). The rest (VPN, a fixed address, company networks, hidden networks) is in KDE's network window:
// More settings at the top. Until 2026-11-14 this row opened KDE's window itself (IPv4/IPv6/802.1x tabs).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Wi-Fi and network")

    readonly property var st: network.state
    readonly property var current: st.networks.find(n => n.connected) || null
    property string openSsid: ""  // the network whose buttons are open

    actions: [
        Kirigami.Action {
            text: L.t("Search again")
            icon.name: "view-refresh"
            visible: page.st.hasWifi && page.st.wifiOn
            enabled: !network.busy
            onTriggered: network.rescan()
        },
        Kirigami.Action {
            text: L.t("More settings")
            icon.name: "network-wireless"
            onTriggered: network.openMore()
        }
    ]

    Component.onCompleted: network.start()
    Component.onDestruction: network.stop()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        // --- Wi-Fi on and off ----------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: !page.st.hasWifi || !page.st.wifiOn ? "network-wireless-disconnected"
                          : page.current ? page.current.icon : "network-wireless"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 2; text: L.t("Wi-Fi") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: !network.loaded ? ""
                            : !page.st.hasWifi ? L.t("This computer has no Wi-Fi adapter. A USB Wi-Fi adapter works too.")
                            : !page.st.wifiOn ? L.t("Wi-Fi is turned off.")
                            : network.connecting ? L.t("Connecting…")
                            : page.current ? L.tf("Connected to {name}", { name: page.current.ssid })
                            : L.t("Not connected")
                    }
                }
                QQC2.Switch {
                    visible: page.st.hasWifi
                    checked: page.st.wifiOn
                    enabled: !network.busy
                    onToggled: network.setWifi(checked)
                }
            }
        }

        // --- The networks around -------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: page.st.hasWifi && page.st.wifiOn
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                RowLayout {
                    Kirigami.Heading { level: 3; text: L.t("Networks"); Layout.fillWidth: true }
                    // only while there is nothing to show yet (not at every look every 10 seconds)
                    QQC2.BusyIndicator { running: network.busy && page.st.networks.length === 0; visible: running; implicitWidth: Kirigami.Units.iconSizes.medium; implicitHeight: implicitWidth }
                }
                Repeater {
                    model: page.st.networks
                    delegate: ColumnLayout {
                        id: entry
                        required property var modelData
                        readonly property bool open: page.openSsid === modelData.ssid
                        readonly property bool failed: network.error.ssid === modelData.ssid
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing

                        QQC2.ItemDelegate {
                            Layout.fillWidth: true
                            onClicked: page.openSsid = entry.open ? "" : entry.modelData.ssid
                            contentItem: RowLayout {
                                spacing: Kirigami.Units.largeSpacing
                                Kirigami.Icon {
                                    source: entry.modelData.icon
                                    implicitWidth: Kirigami.Units.iconSizes.medium
                                    implicitHeight: Kirigami.Units.iconSizes.medium
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        font.bold: entry.modelData.connected
                                        text: entry.modelData.ssid
                                    }
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        opacity: 0.7
                                        font: Kirigami.Theme.smallFont
                                        text: entry.modelData.connected ? L.t("Connected")
                                            : network.connecting === entry.modelData.ssid ? L.t("Connecting…")
                                            : entry.modelData.saved ? L.t("Saved")
                                            : entry.modelData.kind === "open" ? L.t("Open network")
                                            : L.t("Secured")
                                    }
                                }
                                Kirigami.Icon {
                                    visible: entry.modelData.kind !== "open"
                                    source: "object-locked"
                                    implicitWidth: Kirigami.Units.iconSizes.small
                                    implicitHeight: Kirigami.Units.iconSizes.small
                                    opacity: 0.6
                                }
                            }
                        }

                        // the network's buttons (and its password, the first time)
                        ColumnLayout {
                            id: box
                            visible: entry.open
                            Layout.fillWidth: true
                            Layout.leftMargin: Kirigami.Units.iconSizes.medium + Kirigami.Units.largeSpacing * 2
                            Layout.bottomMargin: Kirigami.Units.largeSpacing
                            spacing: Kirigami.Units.smallSpacing
                            readonly property bool needsPassword: !entry.modelData.saved && !entry.modelData.connected
                                                                  && entry.modelData.kind === "personal"
                            QQC2.Label {
                                visible: entry.modelData.kind === "enterprise" && !entry.modelData.saved
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                text: L.t("This network needs a user name too (a company or school network). Set it up in More settings.")
                            }
                            Kirigami.PasswordField {
                                id: password
                                visible: box.needsPassword
                                Layout.fillWidth: true
                                Layout.maximumWidth: Kirigami.Units.gridUnit * 20
                                placeholderText: L.t("Password")
                                onAccepted: if (connectButton.enabled) connectButton.clicked()
                                onVisibleChanged: if (visible) forceActiveFocus()
                            }
                            QQC2.Label {
                                visible: entry.failed
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                color: Kirigami.Theme.negativeTextColor
                                text: network.error.reason === "password"
                                      ? L.t("The password was not accepted. Check it and try again.")
                                      : L.t("Couldn't connect to this network. Try again, or move closer to the router.")
                            }
                            RowLayout {
                                spacing: Kirigami.Units.smallSpacing
                                QQC2.Button {
                                    id: connectButton
                                    visible: !entry.modelData.connected && (entry.modelData.saved || entry.modelData.kind !== "enterprise")
                                    text: L.t("Connect")
                                    icon.name: "network-connect"
                                    enabled: !network.connecting && (!box.needsPassword || password.text.length >= 8)
                                    onClicked: network.connectTo(entry.modelData.ssid, box.needsPassword ? password.text : "")
                                }
                                QQC2.Button {
                                    visible: entry.modelData.kind === "enterprise" && !entry.modelData.saved
                                    text: L.t("More settings")
                                    icon.name: "network-wireless"
                                    onClicked: network.openMore()
                                }
                                QQC2.Button {
                                    visible: entry.modelData.connected
                                    text: L.t("Disconnect")
                                    icon.name: "network-disconnect"
                                    onClicked: network.disconnectWifi()
                                }
                                QQC2.Button {
                                    visible: entry.modelData.saved && network.connecting !== entry.modelData.ssid
                                    text: L.t("Forget")
                                    icon.name: "edit-delete"
                                    onClicked: { network.forget(entry.modelData.ssid); page.openSsid = ""; }
                                }
                                QQC2.BusyIndicator {
                                    visible: network.connecting === entry.modelData.ssid
                                    running: visible
                                    implicitWidth: Kirigami.Units.iconSizes.medium
                                    implicitHeight: implicitWidth
                                }
                            }
                        }
                    }
                }
                QQC2.Label {
                    visible: network.loaded && page.st.networks.length === 0
                    opacity: 0.7
                    text: L.t("No networks found yet.")
                }
            }
        }

        // --- The cable -----------------------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: page.st.hasWired
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: page.st.wiredConnected ? "network-wired-activated" : "network-wired-disconnected"
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 3; text: L.t("Wired connection"); Layout.fillWidth: true }
                    QQC2.Label {
                        Layout.fillWidth: true
                        opacity: 0.8
                        text: page.st.wiredConnected ? L.t("Connected") : L.t("Not connected")
                    }
                }
            }
        }
    }
}
