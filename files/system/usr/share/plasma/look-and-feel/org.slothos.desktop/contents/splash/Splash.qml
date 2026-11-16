pragma ComponentBehavior: Bound
// Sloth OS loading screen after sign-in (KSplash).
// First "Sloth OS" is sprayed on like graffiti and turns into the logo (images/intro.webp, made by
// tools/make_splash_intro.py; it plays once), then the logo pulses until the desktop is ready. The intro's last frame
// is images/logo.png at the same place, so the switch does not show. Without the intro (it cannot be played), the
// pulsing logo comes at once.
import QtQuick

Rectangle {
    id: root
    color: "#1c1e21"

    property int stage

    readonly property int logoSize: Math.min(480, Math.max(160, Math.round(height * 0.32)))
    // the intro: 1200 x 720 with the logo 480 tall in its middle, shown so that its logo is logoSize tall
    readonly property real introScale: logoSize / 480
    property bool introDone: intro.status === AnimatedImage.Error

    AnimatedImage {
        id: intro
        source: "images/intro.webp"
        width: 1200 * root.introScale
        height: 720 * root.introScale
        anchors.centerIn: parent
        smooth: true
        cache: false
        visible: !root.introDone
        onCurrentFrameChanged: {
            if (frameCount > 1 && currentFrame === frameCount - 1) {
                playing = false
                root.introDone = true
            }
        }
    }

    Image {
        id: logo
        source: "images/logo.png"
        width: root.logoSize
        height: root.logoSize
        anchors.centerIn: parent
        smooth: true
        sourceSize.width: 480
        sourceSize.height: 480
        visible: root.introDone

        // a slow, soft pulse while the desktop loads
        SequentialAnimation on scale {
            running: root.introDone
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 1.06; duration: 800; easing.type: Easing.InOutSine }
            NumberAnimation { from: 1.06; to: 1.0; duration: 800; easing.type: Easing.InOutSine }
        }
        SequentialAnimation on opacity {
            running: root.introDone
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.78; duration: 800; easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.78; to: 1.0; duration: 800; easing.type: Easing.InOutSine }
        }
    }

    // At the end of loading it fades out softly
    OpacityAnimator on opacity {
        running: root.stage >= 6
        from: 1
        to: 0
        duration: 400
    }
}
