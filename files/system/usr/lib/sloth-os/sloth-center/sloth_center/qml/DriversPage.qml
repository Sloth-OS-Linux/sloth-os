// Driverek és hardver: videókártya, a megfelelő rendszerváltozat, Secure Boot kulcs.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: "Driverek és hardver"

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
                Kirigami.Heading { level: 3; text: "Videókártya" }
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
                          ? "A Sloth OS NVIDIA-s változata fut, az NVIDIA driver telepítve van. Minden rendben."
                          : "A Sloth OS AMD/Intel változata fut, a driverek a rendszer részei. Minden rendben."
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
                    text: drivers.infoText === "switched" ? "Kész! Indítsd újra a gépet."
                        : drivers.hasNvidia ? "Váltás az NVIDIA-s változatra"
                        : "Váltás az AMD/Intel változatra"
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: !drivers.busy && drivers.infoText !== "switched"
                    text: drivers.hasNvidia
                          ? "A gépedben NVIDIA videókártya van, de a Sloth OS AMD/Intel változata fut. Az NVIDIA-s változattal a játékok sokkal jobban futnak. A fájljaid és beállításaid megmaradnak."
                          : "A gépedben nincs NVIDIA videókártya, ezért az AMD/Intel változat a jobb választás. A fájljaid és beállításaid megmaradnak."
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: drivers.infoText === "switched"
                    text: "Újraindítás után az új változat indul. Ha valami nem stimmel, a Frissítések oldalon visszaállhatsz."
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
                    text: "Váltás most"
                    onClicked: drivers.switchVariant()
                }
                QQC2.Button {
                    visible: drivers.infoText === "switched"
                    icon.name: "system-reboot"
                    text: "Újraindítás most"
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
                    text: drivers.keyPending ? "Még egy lépés: indítsd újra a gépet" : "Az NVIDIA driverhez egy engedély kell"
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    visible: drivers.keyNeeded
                    text: "A gépeden be van kapcsolva a biztonságos rendszerindítás (Secure Boot). Hogy az NVIDIA driver betöltődhessen, egyszer engedélyezni kell a Sloth OS kulcsát. Ez pár kattintás, és utána soha többé nem kell vele foglalkozni."
                }
                QQC2.Button {
                    visible: drivers.keyNeeded
                    highlighted: true
                    icon.name: "security-high"
                    text: "Engedélyezés előkészítése"
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
                        text: "Újraindításkor egy kék képernyő jelenik meg (angolul). Ott a nyilakkal és az Enterrel:"
                    }
                    Repeater {
                        model: [
                            "Nyomj meg egy gombot, amikor a „Press any key” felirat látszik.",
                            "Válaszd: „Enroll MOK”.",
                            "Válaszd: „Continue”, majd „Yes”.",
                            "Jelszónak írd be: universalblue (a képernyőn nem látszik, amit gépelsz).",
                            "Válaszd: „Reboot”. Ennyi!"
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
                        text: "Ha véletlenül kihagyod, semmi gond: a gép elindul, és ez az oldal újra felajánlja."
                    }
                    QQC2.Button {
                        icon.name: "system-reboot"
                        text: "Újraindítás most"
                        onClicked: updates.reboot()
                    }
                }
            }
        }
    }
}
