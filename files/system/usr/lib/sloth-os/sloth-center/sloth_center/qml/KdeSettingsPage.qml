// More settings: the page on the right while the sidebar shows More settings' list (Main.qml: moreMode). The list
// itself (Sloth OS's advanced pages and every KDE settings page, by topic, with a search) is in the sidebar, the same
// way as the everyday rows; a row opens its page here, inside Sloth Center (kde_settings.py).
//
// Until 2026-11-14 this page had the list itself: big topic tiles, a topic's settings as icons after a click (and
// before that four views on a switcher). On the HP it was crowded and took one click more than the rest of the app.
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: page
    property var navigation: null
    title: L.t("More settings")

    Kirigami.PlaceholderMessage {
        anchors.centerIn: parent
        width: Math.min(parent.width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 30)
        icon.name: "preferences-system"
        text: L.t("More settings")
        explanation: L.t("Every other setting of the desktop: keyboard, mouse and touchpad, fonts, windows, shortcuts, the login screen and more. Changes are made with the Apply button under each page.")
    }
}
