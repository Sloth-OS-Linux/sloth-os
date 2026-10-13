// Sloth OS üdvözlő varázsló: első bejelentkezéskor, teljes képernyőn.
// Lépések: üdvözlés -> megjelenés -> appok -> telepítés -> kész.
// Az adatok a Python oldali `welcome` objektumból jönnek.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: "Üdv a Sloth OS-en"
    visible: true
    visibility: Window.FullScreen
    width: Kirigami.Units.gridUnit * 60
    height: Kirigami.Units.gridUnit * 40
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    readonly property int contentWidth: Math.min(width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 52)

    pageStack.initialPage: Kirigami.Page {
        padding: 0
        globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None

        StackLayout {
            anchors.fill: parent
            currentIndex: welcome.page

            // --- 0. Üdvözlés -------------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: root.contentWidth
                    spacing: Kirigami.Units.largeSpacing * 2
                    Image {
                        Layout.alignment: Qt.AlignHCenter
                        source: "file:///usr/share/sloth-os/logo/sloth-logo.svg"
                        sourceSize.width: Kirigami.Units.gridUnit * 10
                        sourceSize.height: Kirigami.Units.gridUnit * 10
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        level: 1
                        text: "Üdv a Sloth OS-en!"
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: "Pár gyors kérdés, és már kész is a géped. Mindent később is megváltoztathatsz."
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        text: "Kezdjük"
                        icon.name: "go-next"
                        highlighted: true
                        onClicked: welcome.next()
                    }
                }
            }

            // --- 1. Megjelenés -----------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: root.contentWidth
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: "Milyen színeket szeretnél?"
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        opacity: 0.8
                        text: "Kattints egyre, és rögtön látod, hogyan néz ki."
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.largeSpacing
                        Repeater {
                            model: welcome.schemes
                            delegate: QQC2.AbstractButton {
                                id: schemeCard
                                required property var modelData
                                readonly property bool current: welcome.currentScheme === modelData.id
                                width: Kirigami.Units.gridUnit * 9
                                height: Kirigami.Units.gridUnit * 7
                                onClicked: welcome.setScheme(modelData.id)
                                contentItem: ColumnLayout {
                                    spacing: Kirigami.Units.smallSpacing
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: Kirigami.Units.cornerRadius
                                        color: schemeCard.modelData.colors[0]
                                        border.width: schemeCard.current ? 3 : 1
                                        border.color: schemeCard.current ? Kirigami.Theme.highlightColor
                                                                         : Qt.rgba(0.5, 0.5, 0.5, 0.4)
                                        Rectangle {
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.bottom: parent.bottom
                                            anchors.margins: Kirigami.Units.largeSpacing
                                            height: Kirigami.Units.gridUnit
                                            radius: height / 3
                                            color: schemeCard.modelData.colors[1]
                                        }
                                        Rectangle {
                                            x: Kirigami.Units.largeSpacing
                                            y: Kirigami.Units.largeSpacing
                                            width: parent.width * 0.5
                                            height: Kirigami.Units.smallSpacing * 2
                                            radius: height / 2
                                            color: schemeCard.modelData.colors[2]
                                        }
                                    }
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        horizontalAlignment: Text.AlignHCenter
                                        text: schemeCard.modelData.name
                                        font.bold: schemeCard.current
                                    }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.largeSpacing
                        QQC2.Button { text: "Vissza"; icon.name: "go-previous"; onClicked: welcome.back() }
                        QQC2.Button { text: "Tovább"; icon.name: "go-next"; highlighted: true; onClicked: welcome.next() }
                    }
                }
            }

            // --- 2. Egy kategória (böngésző, irodai programok, …) -------------
            // Minden kategória külön lépés; ez a lap a welcome.categoryIndex szerinti kategóriát mutatja.
            ColumnLayout {
                id: categoryPage
                readonly property var category: welcome.categoryIndex >= 0 ? welcome.categories[welcome.categoryIndex] : null
                spacing: 0

                QQC2.ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentWidth: availableWidth
                    ColumnLayout {
                        x: (parent.width - width) / 2
                        width: root.contentWidth
                        spacing: Kirigami.Units.largeSpacing * 2

                        Item { implicitHeight: Kirigami.Units.gridUnit * 2 }
                        Kirigami.Icon {
                            Layout.alignment: Qt.AlignHCenter
                            source: categoryPage.category ? categoryPage.category.icon : ""
                            implicitWidth: Kirigami.Units.iconSizes.huge
                            implicitHeight: Kirigami.Units.iconSizes.huge
                        }
                        Kirigami.Heading {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            text: categoryPage.category ? categoryPage.category.name : ""
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: categoryPage.category ? categoryPage.category.hint + " Többet is választhatsz, vagy egyet sem." : ""
                        }
                        Kirigami.InlineMessage {
                            Layout.fillWidth: true
                            visible: !welcome.online
                            type: Kirigami.MessageType.Warning
                            text: "Nincs internetkapcsolat. Az appok telepítéséhez csatlakozz egy hálózathoz."
                            actions: [
                                Kirigami.Action {
                                    text: "Hálózati beállítások"
                                    icon.name: "network-wireless"
                                    onTriggered: welcome.openNetworkSettings()
                                },
                                Kirigami.Action {
                                    text: "Újra"
                                    icon.name: "view-refresh"
                                    onTriggered: welcome.recheckOnline()
                                }
                            ]
                        }

                        Flow {
                            Layout.fillWidth: true
                            Layout.topMargin: Kirigami.Units.largeSpacing
                            spacing: Kirigami.Units.largeSpacing
                            Repeater {
                                model: categoryPage.category ? categoryPage.category.apps : []
                                delegate: QQC2.AbstractButton {
                                    id: appCard
                                    required property var modelData
                                    readonly property bool chosen: welcome.selectedIds.indexOf(modelData.id) !== -1
                                    width: (root.contentWidth - Kirigami.Units.largeSpacing * 2) / 3
                                    height: Kirigami.Units.gridUnit * 4
                                    onClicked: welcome.toggle(modelData.id)
                                    background: Rectangle {
                                        radius: Kirigami.Units.cornerRadius
                                        color: appCard.chosen ? Qt.alpha(Kirigami.Theme.highlightColor, 0.25)
                                             : appCard.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.06)
                                             : Qt.alpha(Kirigami.Theme.textColor, 0.03)
                                        border.width: appCard.chosen ? 2 : 1
                                        border.color: appCard.chosen ? Kirigami.Theme.highlightColor
                                                                     : Qt.alpha(Kirigami.Theme.textColor, 0.12)
                                    }
                                    contentItem: RowLayout {
                                        spacing: Kirigami.Units.largeSpacing
                                        Image {
                                            Layout.leftMargin: Kirigami.Units.largeSpacing
                                            source: appCard.modelData.iconUrl
                                            sourceSize.width: Kirigami.Units.iconSizes.large
                                            sourceSize.height: Kirigami.Units.iconSizes.large
                                            Layout.preferredWidth: Kirigami.Units.iconSizes.large
                                            Layout.preferredHeight: Kirigami.Units.iconSizes.large
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 0
                                            QQC2.Label { text: appCard.modelData.name; font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight }
                                            QQC2.Label { text: appCard.modelData.summary; opacity: 0.7; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; font: Kirigami.Theme.smallFont }
                                        }
                                        Kirigami.Icon {
                                            Layout.rightMargin: Kirigami.Units.largeSpacing
                                            source: appCard.chosen ? "checkbox-checked" : "checkbox-unchecked"
                                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                                            opacity: appCard.chosen ? 1 : 0.5
                                        }
                                    }
                                }
                            }
                        }
                        Item { implicitHeight: Kirigami.Units.gridUnit }
                    }
                }

                // Alsó sáv: lépésjelző, vissza, tovább / telepítés
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: bar.implicitHeight + Kirigami.Units.largeSpacing * 2
                    color: Kirigami.Theme.alternateBackgroundColor
                    RowLayout {
                        id: bar
                        anchors.centerIn: parent
                        width: root.contentWidth
                        QQC2.Label {
                            Layout.fillWidth: true
                            opacity: 0.7
                            text: welcome.stepNumber + ". lépés / " + welcome.stepCount +
                                  (welcome.selectedIds.length > 0 ? "  ·  összesen " + welcome.selectedIds.length + " app kiválasztva" : "")
                        }
                        QQC2.Button { text: "Vissza"; icon.name: "go-previous"; onClicked: welcome.back() }
                        QQC2.Button {
                            highlighted: true
                            enabled: !welcome.lastCategory || welcome.selectedIds.length === 0 || welcome.online
                            text: !welcome.lastCategory ? (welcome.selectedInCategory.length === 0 ? "Kihagyom" : "Tovább")
                                  : welcome.selectedIds.length === 0 ? "Befejezés" : "Telepítés"
                            icon.name: welcome.lastCategory && welcome.selectedIds.length > 0 ? "download" : "go-next"
                            onClicked: {
                                // A böngészős lépés után szólunk, ha nem választott egyet sem
                                if (welcome.categoryIndex === 0 && welcome.selectedInCategory.length === 0)
                                    noBrowser.open();
                                else
                                    welcome.next();
                            }
                        }
                    }
                }
            }

            // --- 3. Telepítés ------------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 30)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Image {
                        Layout.alignment: Qt.AlignHCenter
                        source: "file:///usr/share/sloth-os/logo/sloth-logo.svg"
                        sourceSize.width: Kirigami.Units.gridUnit * 6
                        sourceSize.height: Kirigami.Units.gridUnit * 6
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        level: 2
                        text: welcome.statusText
                    }
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: Math.max(0, welcome.progress)
                        indeterminate: welcome.progress < 0
                    }
                    QQC2.Label {
                        Layout.alignment: Qt.AlignHCenter
                        opacity: 0.7
                        text: welcome.detailText
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.smallSpacing
                        Repeater {
                            model: welcome.selectedIds
                            delegate: RowLayout {
                                id: row
                                required property string modelData
                                readonly property string state: welcome.appStates[modelData] || "waiting"
                                Layout.fillWidth: true
                                spacing: Kirigami.Units.largeSpacing
                                Image {
                                    source: "file:///usr/share/sloth-os/welcome/icons/" + row.modelData + ".png"
                                    sourceSize.width: Kirigami.Units.iconSizes.smallMedium
                                    sourceSize.height: Kirigami.Units.iconSizes.smallMedium
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    text: {
                                        for (const c of welcome.categories)
                                            for (const a of c.apps)
                                                if (a.id === row.modelData) return a.name;
                                        return row.modelData;
                                    }
                                }
                                QQC2.BusyIndicator {
                                    visible: row.state === "installing"
                                    running: visible
                                    implicitWidth: Kirigami.Units.iconSizes.smallMedium
                                    implicitHeight: Kirigami.Units.iconSizes.smallMedium
                                }
                                Kirigami.Icon {
                                    visible: row.state !== "installing"
                                    implicitWidth: Kirigami.Units.iconSizes.smallMedium
                                    implicitHeight: Kirigami.Units.iconSizes.smallMedium
                                    source: row.state === "done" ? "checkmark"
                                          : row.state === "failed" ? "dialog-error" : "content-loading-symbolic"
                                    opacity: row.state === "waiting" ? 0.4 : 1
                                }
                            }
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.6
                        text: "Ez a netkapcsolattól függően pár perc is lehet."
                    }
                }
            }

            // --- 4. Kész -------------------------------------------------------
            Item {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(root.contentWidth, Kirigami.Units.gridUnit * 30)
                    spacing: Kirigami.Units.largeSpacing * 2
                    Image {
                        Layout.alignment: Qt.AlignHCenter
                        source: "file:///usr/share/sloth-os/logo/sloth-logo.svg"
                        sourceSize.width: Kirigami.Units.gridUnit * 8
                        sourceSize.height: Kirigami.Units.gridUnit * 8
                    }
                    Kirigami.Heading {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        level: 2
                        text: welcome.summaryText
                    }
                    Repeater {
                        model: welcome.failures
                        delegate: QQC2.Label {
                            required property var modelData
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            text: "• " + modelData.name + ": " + modelData.error
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        visible: welcome.failures.length > 0
                        text: "A Start menüben a „Sloth Üdvözlő” megnyitásával később újra megpróbálhatod."
                    }
                    QQC2.Button {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Indulhat a móka!"
                        icon.name: "go-next"
                        highlighted: true
                        onClicked: welcome.finish()
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: noBrowser
        title: "Nem választottál böngészőt"
        subtitle: "Böngésző nélkül nem tudsz weboldalakat megnyitni. Biztosan így szeretnéd?"
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: "Választok egyet"
                icon.name: "go-previous"
                onTriggered: noBrowser.close()
            },
            Kirigami.Action {
                text: "Így is jó"
                icon.name: "go-next"
                onTriggered: { noBrowser.close(); welcome.next(); }
            }
        ]
    }
}
