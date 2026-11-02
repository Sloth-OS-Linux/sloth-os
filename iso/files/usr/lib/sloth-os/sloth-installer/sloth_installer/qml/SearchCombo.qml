// A drop-down list with a search field on top (the language, the keyboard and the time zone lists are long: typing
// "buda" finds Europe / Budapest without scrolling). Looks and works like a ComboBox; the choice comes as picked(value).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

QQC2.ComboBox {
    id: combo

    property string value: ""
    property string searchText: ""
    signal picked(string value)

    // what the search finds: every word typed is in the name, upper/lower case and accents do not matter
    function plain(s) {
        return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    }
    readonly property var matches: {
        const words = plain(search.text).split(/\s+/).filter(w => w);
        const all = Array.from(model || []);
        return words.length ? all.filter(item => words.every(w => plain(item[textRole]).includes(w))) : all;
    }

    currentIndex: count > 0 ? indexOfValue(value) : -1

    popup: QQC2.Popup {
        y: combo.height
        width: combo.width
        height: Math.min(Kirigami.Units.gridUnit * 22, combo.Window.height - combo.mapToItem(null, 0, combo.height).y
                         - Kirigami.Units.largeSpacing)
        padding: Kirigami.Units.smallSpacing
        popupType: QQC2.Popup.Item

        onOpened: {
            search.text = "";
            search.forceActiveFocus();
            list.currentIndex = Math.max(0, combo.matches.findIndex(item => item[combo.valueRole] === combo.value));
            list.positionViewAtIndex(list.currentIndex, ListView.Center);
        }

        contentItem: ColumnLayout {
            spacing: Kirigami.Units.smallSpacing

            Kirigami.SearchField {
                id: search
                Layout.fillWidth: true
                placeholderText: combo.searchText
                // the arrows and Enter work in the list while typing
                Keys.onDownPressed: list.incrementCurrentIndex()
                Keys.onUpPressed: list.decrementCurrentIndex()
                Keys.onReturnPressed: list.choose(list.currentIndex)
                Keys.onEnterPressed: list.choose(list.currentIndex)
                onTextChanged: list.currentIndex = 0
            }

            ListView {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: combo.matches
                highlightMoveDuration: 0
                QQC2.ScrollBar.vertical: QQC2.ScrollBar {}

                function choose(i) {
                    if (i < 0 || i >= combo.matches.length) {
                        return;
                    }
                    combo.picked(combo.matches[i][combo.valueRole]);
                    combo.popup.close();
                }

                delegate: QQC2.ItemDelegate {
                    required property var modelData
                    required property int index
                    width: ListView.view.width
                    text: modelData[combo.textRole]
                    highlighted: ListView.isCurrentItem
                    font.bold: modelData[combo.valueRole] === combo.value
                    onClicked: list.choose(index)
                }
            }
        }
    }
}
