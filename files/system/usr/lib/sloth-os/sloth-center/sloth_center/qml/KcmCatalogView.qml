// The list of KDE's settings pages (org.slothos.kcmhost), loaded by KdeSettingsPage.qml through a Loader, so a
// missing module leaves only the list empty.
import QtQuick
import org.slothos.kcmhost

Item {
    readonly property var modules: KcmCatalog.modules()
}
