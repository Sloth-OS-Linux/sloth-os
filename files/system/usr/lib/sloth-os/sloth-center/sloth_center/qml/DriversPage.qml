// Driverek és hardver: videókártya, a megfelelő rendszerváltozat, Secure Boot kulcs.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Driverek és hardver")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: drivers.errorText !== ""
            text: drivers.errorText
        }

        // --- Videókártya -------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Videókártya") }
                Repeater {
                    model: drivers.gpus
                    delegate: RowLayout {
                        id: gpuRow
                        required property var modelData
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "video-display"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        QQC2.Label { text: gpuRow.modelData.name; font.bold: true }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    visible: drivers.canSwitch && !drivers.mismatch
                    text: drivers.nvidiaImage
                          ? L.t("A Sloth OS NVIDIA-s változata fut, az NVIDIA driver telepítve van. Minden rendben.")
                          : L.t("A Sloth OS AMD/Intel változata fut, a driverek a rendszer részei. Minden rendben.")
                }
            }
        }

        // --- Rossz változat fut ---------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: drivers.mismatch || drivers.busy || drivers.infoText === "switched"
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading {
                    level: 3
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: drivers.infoText === "switched" ? L.t("Kész! Indítsd újra a gépet.")
                        : drivers.hasNvidia ? L.t("Váltás az NVIDIA-s változatra")
                        : L.t("Váltás az AMD/Intel változatra")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: !drivers.busy && drivers.infoText !== "switched"
                    text: drivers.hasNvidia
                          ? L.t("A gépedben NVIDIA videókártya van, de a Sloth OS AMD/Intel változata fut. Az NVIDIA-s változattal a játékok sokkal jobban futnak. A fájljaid és beállításaid megmaradnak.")
                          : L.t("A gépedben nincs NVIDIA videókártya, ezért az AMD/Intel változat a jobb választás. A fájljaid és beállításaid megmaradnak.")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: drivers.infoText === "switched"
                    text: L.t("Újraindítás után az új változat indul. Ha valami nem stimmel, a Frissítések oldalon visszaállhatsz.")
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: drivers.busy
                    QQC2.Label { text: drivers.statusText }
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        from: 0; to: 100
                        value: Math.max(0, drivers.progress)
                        indeterminate: drivers.progress < 0
                    }
                    QQC2.Label { opacity: 0.7; text: drivers.infoText }
                }
                QQC2.Button {
                    visible: !drivers.busy && drivers.infoText !== "switched"
                    highlighted: true
                    icon.name: "download"
                    text: L.t("Váltás most")
                    onClicked: drivers.switchVariant()
                }
                QQC2.Button {
                    visible: drivers.infoText === "switched"
                    icon.name: "system-reboot"
                    text: L.t("Újraindítás most")
                    onClicked: updates.reboot()
                }
            }
        }

        // --- Secure Boot kulcs ---------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: drivers.keyNeeded || drivers.keyPending
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading {
                    level: 3
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: drivers.keyPending ? L.t("Még egy lépés: indítsd újra a gépet") : L.t("Az NVIDIA driverhez egy engedély kell")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: drivers.keyNeeded
                    text: L.t("A gépeden be van kapcsolva a biztonságos rendszerindítás (Secure Boot). Hogy az NVIDIA driver betöltődhessen, egyszer engedélyezni kell a Sloth OS kulcsát. Ez pár kattintás, és utána soha többé nem kell vele foglalkozni.")
                }
                QQC2.Button {
                    visible: drivers.keyNeeded
                    highlighted: true
                    icon.name: "security-high"
                    text: L.t("Engedélyezés előkészítése")
                    onClicked: drivers.enrollKey()
                }
                // Lépésről lépésre a kék képernyőhöz (azt a gép firmware-e mutatja, angolul)
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: drivers.keyPending
                    spacing: Kirigami.Units.smallSpacing
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: L.t("Újraindításkor egy kék képernyő jelenik meg (angolul). Ott a nyilakkal és az Enterrel:")
                    }
                    Repeater {
                        model: [
                            L.t("Nyomj meg egy gombot, amikor a „Press any key” felirat látszik."),
                            L.t("Válaszd: „Enroll MOK”."),
                            L.t("Válaszd: „Continue”, majd „Yes”."),
                            L.t("Jelszónak írd be: universalblue (a képernyőn nem látszik, amit gépelsz)."),
                            L.t("Válaszd: „Reboot”. Ennyi!")
                        ]
                        delegate: QQC2.Label {
                            required property string modelData
                            required property int index
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: (index + 1) + ". " + modelData
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: L.t("Ha véletlenül kihagyod, semmi gond: a gép elindul, és ez az oldal újra felajánlja.")
                    }
                    QQC2.Button {
                        icon.name: "system-reboot"
                        text: L.t("Újraindítás most")
                        onClicked: updates.reboot()
                    }
                }
            }
        }

        // --- Kontrollerek -------------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Kontrollerek") }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: gamepads.gamepads.length === 0
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("Most nincs csatlakoztatott kontroller. Dugd be kábellel, vagy párosítsd Bluetooth-on. Az Xbox, PlayStation, Nintendo Switch és Steam kontrollerek külön telepítés nélkül működnek.")
                }
                Repeater {
                    model: gamepads.gamepads
                    delegate: RowLayout {
                        id: padRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: "input-gamepad"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: Kirigami.Units.iconSizes.medium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: padRow.modelData.name; font.bold: true }
                            QQC2.Label {
                                Layout.fillWidth: true
                                opacity: 0.7
                                text: gamepads.connectionText(padRow.modelData.connection)
                            }
                        }
                        Kirigami.Icon {
                            visible: padRow.modelData.battery >= 0
                            source: padRow.modelData.charging ? "battery-charging" : padRow.modelData.battery < 20 ? "battery-caution" : "battery"
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }
                        QQC2.Label {
                            visible: padRow.modelData.battery >= 0
                            text: padRow.modelData.battery + "%"
                        }
                    }
                }
                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        icon.name: "preferences-system-bluetooth"
                        text: L.t("Vezeték nélküli kontroller párosítása")
                        onClicked: gamepads.openSettings("kcm_bluetooth")
                    }
                    QQC2.Button {
                        enabled: gamepads.gamepads.length > 0
                        icon.name: "input-gamepad"
                        text: L.t("Gombok kipróbálása")
                        onClicked: gamepads.openSettings("kcm_gamecontroller")
                    }
                }
            }
        }

        // --- Telefon összekötése (KDE Connect) ------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: drivers.phoneLinkAvailable
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("Telefon összekötése") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("A telefonod értesítései, fájljai és üzenetei a gépen (KDE Connect). A telefonra a KDE Connect appot kell telepíteni, és mindkettőnek ugyanazon a Wi-Fi-hálózaton kell lennie.")
                    }
                }
                QQC2.Switch {
                    checked: drivers.phoneLink
                    onToggled: drivers.setPhoneLink(checked)
                }
            }
        }
    }

    // Kontroller csatlakoztatása, leválasztása, akkuszint: pár másodpercenként frissül
    Timer {
        interval: 3000
        running: page.visible
        repeat: true
        onTriggered: gamepads.refresh()
    }
}
