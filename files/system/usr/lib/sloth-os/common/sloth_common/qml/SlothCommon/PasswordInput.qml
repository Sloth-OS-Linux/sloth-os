// A password field whose Tab goes on to the next field, not to its own show-password button first (Kirigami's
// PasswordField puts that button in the focus chain; reported for the installer and the PIN on 2026-10-30 and for
// the folder sharing password on 2026-11-02). The button still works with the mouse.
import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.PasswordField {
    id: field

    function inside(item) {
        for (let p = item; p; p = p.parent) {
            if (p === field)
                return true;
        }
        return false;
    }

    function skipOwnButtons(forward) {
        let next = nextItemInFocusChain(forward);
        while (next && next !== field && inside(next))
            next = next.nextItemInFocusChain(forward);
        if (next && next !== field)
            next.forceActiveFocus(forward ? Qt.TabFocusReason : Qt.BacktabFocusReason);
    }

    // the button is taken out of the Tab order (so Shift+Tab from the next field comes back to the text too)
    function untab(item) {
        for (const child of item.children) {
            if (child.activeFocusOnTab !== undefined)
                child.activeFocusOnTab = false;
            untab(child);
        }
    }

    Component.onCompleted: Qt.callLater(() => untab(field))
    Keys.onTabPressed: skipOwnButtons(true)
    Keys.onBacktabPressed: skipOwnButtons(false)
}
