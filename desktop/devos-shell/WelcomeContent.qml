import QtQuick
import QtQuick.Layouts

// Welcome content (SRS §7.2). Hosted by Welcome.qml; `host` owns state and actions.
Item {
    id: content
    required property var host
    readonly property var win: host

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 36
        spacing: 18

        RowLayout {
            spacing: 14
            Rectangle {
                width: 52; height: 52; radius: 15
                color: "#0e1521"
                border.width: 2
                border.color: Theme.teal
                Text { anchors.centerIn: parent; text: "›_"; color: Theme.teal
                       font.family: Theme.mono; font.pixelSize: 22; font.weight: Font.Bold }
            }
            ColumnLayout {
                spacing: 2
                Text { text: "Welcome to DevOS"; color: Theme.text; font.family: Theme.display
                       font.pixelSize: 28; font.weight: Font.Bold }
                Text { text: "Your development environment is ready. Two optional steps:"; color: Theme.muted
                       font.pixelSize: 14 }
            }
        }

        Text { text: "1 · Developer profiles"; color: Theme.text; font.pixelSize: 16; font.weight: Font.DemiBold }
        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "The General profile (Git, C/C++, Python, Node/TypeScript, Go, Rust, Neovim, Podman) is installed. Add more:"
            color: Theme.muted
            font.pixelSize: 13
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            rowSpacing: 8
            columnSpacing: 8
            Repeater {
                model: win.profiles
                Rectangle {
                    required property var modelData
                    readonly property bool isInstalled: !!win.installed[modelData.id]
                    readonly property bool isSelected: isInstalled || !!win.selected[modelData.id]
                    Layout.fillWidth: true
                    implicitHeight: 58
                    radius: 12
                    color: isSelected ? Qt.rgba(0.18, 0.83, 0.75, 0.10) : Theme.surface
                    border.color: isSelected ? Qt.rgba(0.18, 0.83, 0.75, 0.5) : Theme.border
                    MouseArea {
                        anchors.fill: parent
                        enabled: !parent.isInstalled
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            const s = Object.assign({}, win.selected);
                            s[parent.modelData.id] = !s[parent.modelData.id];
                            win.selected = s;
                        }
                    }
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 2
                        Text { text: modelData.title + (isInstalled ? "  ·  installed" : "")
                               color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold }
                        Text { text: modelData.desc; color: Theme.faint; font.pixelSize: 12
                               elide: Text.ElideRight; Layout.fillWidth: true }
                    }
                }
            }
        }
        DButton {
            label: "Install selected profiles"
            enabled: Object.keys(win.selected).some(k => win.selected[k] && !win.installed[k])
            opacity: enabled ? 1 : 0.5
            onClicked: win.installSelected()
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

        Text { text: "2 · DevOS AI (optional)"; color: Theme.text; font.pixelSize: 16; font.weight: Font.DemiBold }
        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            // FB-003: AI is optional; DevOS is fully usable without it.
            text: win.client.keyStatus === "missing" || win.client.keyStatus === "unknown"
                ? "Connect your own Google Gemini API key to use the AI assistant and agent. You can do this any time with Super+A."
                : "Gemini is connected (" + win.client.keyStatus + "). Open the panel any time with Super+A."
            color: Theme.muted
            font.pixelSize: 13
        }
        RowLayout {
            spacing: 8
            DButton { label: "Configure Gemini"; variant: "primary"; onClicked: { win.openAiPanel(); win.finish(); } }
            DButton { label: "Skip"; onClicked: win.finish() }
        }

        Item { Layout.fillHeight: true }
        RowLayout {
            Text { text: "Reopen this window from the launcher: DevOS Welcome"; color: Theme.faint; font.pixelSize: 12
                   Layout.fillWidth: true }
            DButton { label: "Done"; onClicked: win.finish() }
        }
    }
}
