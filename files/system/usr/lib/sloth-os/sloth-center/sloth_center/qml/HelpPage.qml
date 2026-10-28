// Help that works without internet: the most common problems, in plain words, each with a button to the page that
// fixes it. Everything here is part of Sloth Center itself, nothing is downloaded (ROADMAP: offline help).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Help")
    property var navigation: null  // Main.qml, to open the page an answer points to

    // Each answer: the question, the answer, and the module it points to (Main.qml "modules" ids; "" = none)
    readonly property var topics: [
        { title: L.t("Sloth OS doesn't start"),
          text: L.t("If a start doesn't reach the login screen, the next start shows a menu by itself. You can also bring it up by pressing Esc or Shift while the computer starts. Choose the second entry: that is the previous version, and your files stay. If the desktop still doesn't come up, choose “Reset this PC” in the same menu: your files stay then too."),
          module: "" },
        { title: L.t("An update caused trouble"),
          text: L.t("On the Updates page, “Back to the previous version” returns to the version before the update. Your files and settings stay."),
          module: "updates" },
        { title: L.t("No internet or Wi-Fi"),
          text: L.t("System status → Check Wi-Fi goes through it step by step: the adapter, the switch, the network, the signal and the internet."),
          module: "status" },
        { title: L.t("A file is missing or was overwritten"),
          text: L.t("File backup keeps the state of your files every hour. You can restore a file or find deleted ones there."),
          module: "backup" },
        { title: L.t("A Windows program or game doesn't start"),
          text: L.t("Programs can repair or reinstall it. On the Games page, “Will it run?” tells whether other players could run it, and why not if it is blocked. If it still doesn't work, tell us on the Feedback page."),
          module: "winprograms" },
        { title: L.t("No sound, or the wrong speaker"),
          text: L.t("Drivers and hardware → Sound: choose the speakers or headphones, play a test sound, and test the microphone."),
          module: "drivers" },
        { title: L.t("The screen looks wrong"),
          text: L.t("Drivers and hardware → Displays: the main screen, the refresh rate and the size. If you don't keep a change, it goes back by itself after 15 seconds."),
          module: "drivers" },
        { title: L.t("Install Sloth OS again, or on another computer"),
          text: L.t("Create installation media shows how to make a USB stick. Before reinstalling, save your Sloth OS settings to a file on the File backup page."),
          module: "usbguide" },
        { title: L.t("Ask for help"),
          text: L.t("Feedback sends your description to the Sloth OS developers. That needs internet; everything else on this page works without it."),
          module: "feedback" }
    ]

    function moduleName(id) {
        const m = navigation ? navigation.modules.find(m => m.id === id) : null;
        return m ? m.name : "";
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        QQC2.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.8
            text: L.t("The most common problems and where to fix them. This help works without internet too.")
        }

        Repeater {
            model: page.topics
            delegate: Kirigami.AbstractCard {
                id: topicCard
                required property var modelData
                Layout.fillWidth: true
                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { Layout.fillWidth: true; level: 3; wrapMode: Text.Wrap; text: topicCard.modelData.title }
                    QQC2.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: topicCard.modelData.text }
                    QQC2.Button {
                        visible: topicCard.modelData.module !== "" && page.navigation !== null
                        text: L.tf("Open {page}", { page: page.moduleName(topicCard.modelData.module) })
                        icon.name: "go-next"
                        onClicked: page.navigation.openModuleById(topicCard.modelData.module)
                    }
                }
            }
        }
    }
}
