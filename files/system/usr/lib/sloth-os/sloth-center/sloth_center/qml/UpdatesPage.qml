// Updates and rollback. Only a human-language status and a progress bar,
// never terminal output. The data comes from the Python side's `updates` object.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: L.t("Updates")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing * 2

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: updates.unavailableText !== ""
            text: updates.unavailableText
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Error
            visible: updates.errorText !== ""
            text: updates.errorText
            showCloseButton: true
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Positive
            visible: updates.infoText !== "" && !updates.busy
            text: updates.infoText
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: updates.signatureVerified ? Kirigami.MessageType.Positive : Kirigami.MessageType.Warning
            text: updates.signatureVerified
                  ? L.t("Verified updates ✓ – this system only accepts updates signed by Sloth OS.")
                  : L.t("Update signature checking is not enabled. This system may accept unsigned updates.")
        }

        // --- Main status ------------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

                RowLayout {
                    spacing: Kirigami.Units.largeSpacing * 2
                    Kirigami.Icon {
                        implicitWidth: Kirigami.Units.iconSizes.huge
                        implicitHeight: Kirigami.Units.iconSizes.huge
                        source: updates.busy ? "system-software-update"
                              : updates.needsReboot ? "system-reboot"
                              : updates.updateAvailable ? "update-high"
                              : "security-high"
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            level: 2
                            text: updates.busy ? updates.statusText
                                : updates.needsReboot ? L.t("Restart needed")
                                : updates.updateAvailable ? L.t("A new update is available")
                                : L.t("Your system is up to date")
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.8
                            text: updates.needsReboot && !updates.busy
                                  ? L.tf("After a restart, this starts: {version}", { version: updates.pendingVersion })
                                  : updates.updateAvailable && !updates.busy && updates.downloadSize !== ""
                                  ? L.tf("Available version: {version} (download: {size})", { version: updates.availableVersion, size: updates.downloadSize })
                                  : updates.updateAvailable && !updates.busy
                                  ? L.tf("Available version: {version}", { version: updates.availableVersion })
                                  : L.tf("Current version: {version}", { version: updates.currentVersion || "–" })
                        }
                    }
                }

                // Progress bar: a percentage if we know it; otherwise a moving bar
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: updates.busy
                    spacing: Kirigami.Units.smallSpacing
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: Math.max(0, updates.progress)
                        indeterminate: updates.progress < 0
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        visible: updates.detailText !== "" || updates.progress >= 0
                        QQC2.Label {
                            Layout.fillWidth: true
                            opacity: 0.7
                            text: updates.detailText
                        }
                        QQC2.Label {
                            visible: updates.progress >= 0
                            opacity: 0.7
                            text: updates.progress + "%"
                        }
                    }
                }

                RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    QQC2.Button {
                        visible: !updates.busy && !updates.needsReboot && !updates.updateAvailable
                        enabled: updates.unavailableText === ""
                        icon.name: "view-refresh"
                        text: L.t("Check for updates")
                        onClicked: updates.checkForUpdates()
                    }
                    QQC2.Button {
                        visible: !updates.busy && !updates.needsReboot && updates.updateAvailable
                        icon.name: "download"
                        text: L.t("Install update")
                        onClicked: updates.installUpdate()
                    }
                    QQC2.Button {
                        id: restartButton
                        // The restart takes a few seconds to show; without feedback the button got clicked again and
                        // again (Reddit, 2026-10-30). If nothing happens in a minute, it can be clicked again.
                        property bool restarting: false
                        visible: !updates.busy && updates.needsReboot
                        enabled: !restarting
                        icon.name: "system-reboot"
                        text: restarting ? L.t("Restarting…") : L.t("Restart now")
                        onClicked: { restarting = true; restartReset.restart(); updates.reboot(); }
                        Timer { id: restartReset; interval: 60000; onTriggered: restartButton.restarting = false }
                    }
                    QQC2.BusyIndicator {
                        visible: restartButton.restarting && restartButton.visible
                        running: visible
                        Layout.preferredHeight: restartButton.height
                        Layout.preferredWidth: restartButton.height
                    }
                    QQC2.Button {
                        visible: updates.busy && (updates.mode === "check" || updates.mode === "upgrade")
                        icon.name: "dialog-cancel"
                        text: L.t("Cancel")
                        onClicked: updates.cancel()
                    }
                }

                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    visible: !updates.busy
                    text: L.t("The update downloads the parts your system needs, so its size varies. Keep some free disk space for the download and the new system version. It is prepared in the background; you can keep working, and it takes effect after a restart.")
                }
            }
        }

        // --- Apps: Discover and the automatic app updates ------------------------------------
        // This page updates the system; the apps (Flatpak) are updated in the background by a daily updater, by hand in
        // Discover; Discover does not show the system update (there are not two separate system updates)
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon {
                    source: "plasmadiscover"
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: Kirigami.Units.iconSizes.medium
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 3; text: L.t("Apps"); Layout.fillWidth: true }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: L.t("Apps (the ones you installed in Welcome or Discover) update themselves once a day, unless you're on a mobile or other metered connection. Windows programs and game stores (such as Steam or Battle.net) update themselves.")
                    }
                }
                QQC2.Button {
                    text: L.t("Open in Discover")
                    icon.name: "plasmadiscover"
                    onClicked: updates.openDiscover()
                }
            }
        }

        // --- When the automatic system update downloads (rpm-ostreed-automatic.timer, sloth-helper update-time) ---
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: updates.updateHour >= 0
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 3; text: L.t("When system updates download"); Layout.fillWidth: true }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        text: L.t("Every day at this time, or when you next turn the computer on if it was off then. Never on a mobile or other metered connection.")
                    }
                }
                QQC2.ComboBox {
                    // a list, not a spin box: every change asks for administrator approval once
                    Accessible.name: L.t("When system updates download")
                    model: Array.from({ length: 24 }, (_, h) => (h < 10 ? "0" : "") + h + ":00")
                    currentIndex: Math.max(0, updates.updateHour)
                    onActivated: index => {
                        if (index !== updates.updateHour)
                            updates.setUpdateHour(index)
                        // shows what is really set (also if the password prompt was cancelled)
                        currentIndex = Qt.binding(() => Math.max(0, updates.updateHour))
                    }
                }
            }
        }

        // --- Quiet hours: no notification asks for a restart then (sloth_common.quiet_hours) ---
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Kirigami.Heading { level: 3; text: L.t("Quiet hours"); Layout.fillWidth: true }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            opacity: 0.7
                            text: L.t("In this part of the day no notification asks you to restart, for example while you play in the evening. It comes when the quiet hours end; nothing restarts by itself.")
                        }
                    }
                    QQC2.Switch {
                        id: quietSwitch
                        Accessible.name: L.t("Quiet hours")
                        checked: updates.quietHours.enabled
                        onToggled: updates.setQuietHours(checked, quietStart.value, quietEnd.value)
                    }
                }
                RowLayout {
                    id: quietTimes
                    enabled: quietSwitch.checked
                    spacing: Kirigami.Units.largeSpacing
                    // the times are minutes after midnight: the arrows step 15 minutes, any time can be typed
                    function clockText(v) {
                        const h = Math.floor(v / 60), m = v % 60
                        return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m
                    }
                    function clockValue(text, fallback) {
                        // "21:30", "21.30", "2130" or "21"
                        const t = text.trim().match(/^(\d{1,2})(?:[:.]?(\d{2}))?$/)
                        if (!t || Number(t[1]) > 23 || Number(t[2] || 0) > 59)
                            return fallback
                        return Number(t[1]) * 60 + Number(t[2] || 0)
                    }
                    QQC2.Label { text: L.t("From") }
                    QQC2.SpinBox {
                        id: quietStart
                        from: 0; to: 24 * 60 - 1; stepSize: 15; wrap: true; editable: true
                        value: updates.quietHours.start
                        textFromValue: (v, locale) => quietTimes.clockText(v)
                        valueFromText: (text, locale) => quietTimes.clockValue(text, value)
                        validator: RegularExpressionValidator { regularExpression: /^\d{0,2}[:.]?\d{0,2}$/ }
                        onValueModified: updates.setQuietHours(quietSwitch.checked, value, quietEnd.value)
                    }
                    QQC2.Label { text: L.t("to") }
                    QQC2.SpinBox {
                        id: quietEnd
                        from: 0; to: 24 * 60 - 1; stepSize: 15; wrap: true; editable: true
                        value: updates.quietHours.end
                        textFromValue: (v, locale) => quietTimes.clockText(v)
                        valueFromText: (text, locale) => quietTimes.clockValue(text, value)
                        validator: RegularExpressionValidator { regularExpression: /^\d{0,2}[:.]?\d{0,2}$/ }
                        onValueModified: updates.setQuietHours(quietSwitch.checked, quietStart.value, value)
                    }
                }
            }
        }

        // --- Keeping a version ---------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Heading { level: 3; text: L.t("Keep the current version") }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                        text: L.t("If everything works well now, you can mark this version. Later updates won't delete it, so if a newer version has problems, you can always go back to this one.")
                    }
                }
                QQC2.Switch {
                    checked: updates.pinned
                    enabled: updates.canPin
                    onToggled: updates.setPinned(checked)
                }
            }
        }

        // --- Rollback -----------------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading {
                    level: 3
                    text: L.t("Roll back to the previous version")
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: updates.rollbackVersion !== ""
                          ? L.tf("If something hasn't worked right since the last update, you can go back to the previous version ({version}). Your files and settings are kept.", { version: updates.rollbackVersion })
                          : L.t("There's no earlier version to go back to yet.")
                }
                QQC2.Button {
                    enabled: updates.canRollback
                    icon.name: "edit-undo"
                    text: L.t("Back to the previous version")
                    onClicked: confirmRollback.open()
                }
            }
        }

        // --- Every version on the machine ----------------------------------------------
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: updates.versions.length > 1
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Heading { level: 3; text: L.t("Versions on this computer") }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.8
                    text: L.t("These system versions are on the computer now. You can start any of them at the next restart, without downloading anything. Updates do not delete the kept ones.")
                }
                Repeater {
                    model: updates.versions
                    delegate: RowLayout {
                        id: verRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: verRow.modelData.booted ? "emblem-default" : "system-software-update"
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; elide: Text.ElideRight; text: verRow.modelData.name }
                            QQC2.Label {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                opacity: 0.7
                                font: Kirigami.Theme.smallFont
                                text: [verRow.modelData.booted ? L.t("running now") : "",
                                       verRow.modelData.next ? L.t("starts next time") : "",
                                       verRow.modelData.pinned ? L.t("kept") : ""].filter(x => x).join(" · ")
                            }
                        }
                        QQC2.Button {
                            visible: !verRow.modelData.next
                            enabled: !updates.busy
                            icon.name: "system-reboot"
                            text: L.t("Start this one next time")
                            onClicked: updates.bootVersion(verRow.modelData.index)
                        }
                        QQC2.CheckBox {
                            text: L.t("Keep")
                            checked: verRow.modelData.pinned
                            enabled: !updates.busy
                            onToggled: updates.setVersionPinned(verRow.modelData.index, checked)
                        }
                    }
                }
            }
        }
    }

    // Installing on a mobile or other metered connection: ask first (the download can cost money)
    Connections {
        target: updates
        function onChanged() {
            if (updates.meteredWarning && !confirmMetered.opened)
                confirmMetered.open()
            else if (!updates.meteredWarning && confirmMetered.opened)
                confirmMetered.close()
        }
    }

    Kirigami.PromptDialog {
        id: confirmMetered
        title: L.t("Download on a metered connection?")
        subtitle: updates.downloadSize !== ""
                  ? L.tf("You're on a mobile or other metered connection, and this update downloads about {size}. That can use up your data plan. You can also wait for Wi-Fi or a cable connection: the update then downloads by itself.", { size: updates.downloadSize })
                  : L.t("You're on a mobile or other metered connection, and a system update usually downloads several gigabytes. That can use up your data plan. You can also wait for Wi-Fi or a cable connection: the update then downloads by itself.")
        standardButtons: Kirigami.Dialog.NoButton
        // closed with Esc or the X too
        onClosed: if (updates.meteredWarning) updates.dismissMeteredWarning()
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Download anyway")
                icon.name: "download"
                onTriggered: updates.installUpdateAnyway()
            },
            Kirigami.Action {
                text: L.t("Later")
                icon.name: "dialog-cancel"
                onTriggered: updates.dismissMeteredWarning()
            }
        ]
    }

    Kirigami.PromptDialog {
        id: confirmRollback
        title: L.t("Go back to the previous version?")
        subtitle: L.tf("After a restart, the previous version ({version}) starts. Your files and settings are kept, and you can update again later.", { version: updates.rollbackVersion })
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.t("Go back")
                icon.name: "edit-undo"
                onTriggered: { confirmRollback.close(); updates.rollback(); }
            },
            Kirigami.Action {
                text: L.t("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirmRollback.close()
            }
        ]
    }
}
