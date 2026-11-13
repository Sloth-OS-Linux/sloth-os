// One KDE settings page in Sloth Center's window (org.slothos.kcmhost, built into the image). In a file of its own,
// loaded by KcmPage.qml through a Loader: if the module is missing, only that Loader fails and the page opens in its
// own window instead (kde_settings.py).
import QtQuick
import org.slothos.kcmhost

KcmView {}
