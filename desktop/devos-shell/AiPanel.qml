import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

// The DevOS AI panel (SRS §20): a layer-shell sidebar on the right.
PanelWindow {
    id: win
    required property var client
    property bool open: false
    property bool showHistory: false

    visible: open
    anchors { top: true; right: true; bottom: true }
    margins { top: 8; right: 8; bottom: 8 }
    implicitWidth: 520
    exclusiveZone: 0
    color: "transparent"
    WlrLayershell.namespace: "devos-ai"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: open ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

    onOpenChanged: if (open) { client.ensureConnected(); input.forceActiveFocus(); }

    function denyPending() {
        for (let i = client.items.count - 1; i >= 0; i--) {
            const it = client.items.get(i);
            if (it.kind === "approval" && !it.resolved) { client.respond(it.approvalId, "deny"); return true; }
        }
        return false;
    }

    Rectangle {
        anchors.fill: parent
        radius: 18
        color: Theme.bg
        border.color: Theme.border

        FocusScope {
            anchors.fill: parent
            focus: true
            // Esc denies a pending approval, otherwise closes the panel (UX-001).
            Keys.onEscapePressed: if (!win.denyPending()) win.open = false

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                // ---------------------------------------------------- header
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Rectangle {
                        width: 30; height: 30; radius: 9
                        color: "#0e1521"
                        border.width: 1.5
                        border.color: Theme.teal
                        Text {
                            anchors.centerIn: parent
                            text: "›_"
                            color: Theme.teal
                            font.family: Theme.mono
                            font.pixelSize: 13
                            font.weight: Font.Bold
                        }
                    }
                    ColumnLayout {
                        spacing: 0
                        Text {
                            text: "DevOS AI"
                            color: Theme.text
                            font.family: Theme.display
                            font.pixelSize: 17
                            font.weight: Font.Bold
                        }
                        Text {
                            text: win.client.model ? "Gemini · " + win.client.model : "Gemini"
                            color: Theme.faint
                            font.pixelSize: 11
                        }
                    }
                    Item { Layout.fillWidth: true }
                    // Status (SRS §20.3) and the external-provider indicator (PRIV-012)
                    Rectangle {
                        implicitHeight: 24
                        implicitWidth: statusRow.implicitWidth + 16
                        radius: 12
                        color: Theme.surface
                        border.color: Theme.border
                        RowLayout {
                            id: statusRow
                            anchors.centerIn: parent
                            spacing: 6
                            Rectangle {
                                width: 7; height: 7; radius: 4
                                color: ({ off: Theme.faint, idle: Theme.success, thinking: Theme.violet,
                                          running: Theme.teal, waiting: Theme.warning, error: Theme.danger })[win.client.status]
                                SequentialAnimation on opacity {
                                    running: win.client.status === "thinking" || win.client.status === "running"
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 0.3; duration: 500 }
                                    NumberAnimation { to: 1; duration: 500 }
                                }
                            }
                            Text {
                                text: win.client.status === "thinking" ? "sending to Gemini" : win.client.status
                                color: Theme.muted
                                font.pixelSize: 11
                            }
                        }
                    }
                    DButton { label: "History"; variant: "ghost"; small: true
                              onClicked: { win.showHistory = !win.showHistory; if (win.showHistory) win.client.loadConversations(); } }
                    DButton { label: "New"; variant: "ghost"; small: true
                              onClicked: { win.showHistory = false; win.client.newConversation(); } }
                    DButton { label: "✕"; variant: "ghost"; small: true; onClicked: win.open = false }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

                // ------------------------------------------------------ body
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    Text {
                        visible: !win.client.connected
                        anchors.centerIn: parent
                        width: parent.width - 40
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: "Connecting to devosd…\nIf this persists: systemctl --user start devosd.socket"
                        color: Theme.muted
                        font.pixelSize: 13
                    }

                    KeySetup {
                        visible: win.client.connected && win.client.keyStatus === "missing"
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        client: win.client
                    }

                    ListView {
                        id: history
                        visible: win.client.connected && win.client.keyStatus !== "missing" && win.showHistory
                        anchors.fill: parent
                        clip: true
                        spacing: 6
                        model: win.client.conversations
                        delegate: Rectangle {
                            required property string id
                            required property string title
                            required property string mode
                            required property string workspace
                            width: history.width
                            height: 52
                            radius: 10
                            color: hov.containsMouse ? Theme.surfaceHigh : Theme.surface
                            MouseArea {
                                id: hov
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: { win.client.openConversation(parent.id); win.showHistory = false; }
                            }
                            ColumnLayout {
                                anchors.left: parent.left
                                anchors.right: del.left
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 12
                                spacing: 2
                                Text { text: title; color: Theme.text; font.pixelSize: 13; elide: Text.ElideRight
                                       Layout.fillWidth: true }
                                Text { text: mode + (workspace ? " · " + workspace : ""); color: Theme.faint
                                       font.pixelSize: 11; elide: Text.ElideMiddle; Layout.fillWidth: true }
                            }
                            DButton { id: del; anchors.right: parent.right; anchors.rightMargin: 10
                                      anchors.verticalCenter: parent.verticalCenter
                                      label: "Delete"; variant: "danger"; small: true
                                      onClicked: win.client.deleteConversation(parent.id) }
                        }
                    }

                    ListView {
                        id: chat
                        visible: win.client.connected && win.client.keyStatus !== "missing" && !win.showHistory
                        anchors.fill: parent
                        clip: true
                        spacing: 0   // rows carry their own bottom gap; collapsed rows take none
                        model: win.client.items
                        delegate: ChatItem { client: win.client }
                        onCountChanged: Qt.callLater(() => chat.positionViewAtEnd())
                        onContentHeightChanged: if (atYEnd || moving === false) Qt.callLater(() => chat.positionViewAtEnd())

                        Text {
                            visible: chat.count === 0
                            anchors.centerIn: parent
                            width: parent.width - 60
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: win.client.mode === "agent"
                                ? "Agent mode: the agent can inspect your project and run tools. Changes always ask for your approval."
                                : "Ask anything. Switch to Agent to let DevOS AI work on a project."
                            color: Theme.faint
                            font.pixelSize: 13
                            lineHeight: 1.3
                        }
                    }
                }

                // ---------------------------------------------------- footer
                ColumnLayout {
                    visible: win.client.connected && win.client.keyStatus !== "missing"
                    Layout.fillWidth: true
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        // Chat | Agent (AI-009)
                        Rectangle {
                            implicitWidth: seg.implicitWidth + 6
                            implicitHeight: 30
                            radius: 9
                            color: Theme.surface
                            border.color: Theme.border
                            Row {
                                id: seg
                                anchors.centerIn: parent
                                spacing: 2
                                Repeater {
                                    model: ["chat", "agent"]
                                    Rectangle {
                                        required property string modelData
                                        width: 64; height: 24; radius: 7
                                        color: win.client.mode === modelData ? Theme.surfaceHigh : "transparent"
                                        border.color: win.client.mode === modelData ? Theme.teal : "transparent"
                                        Text { anchors.centerIn: parent
                                               text: modelData === "chat" ? "Chat" : "Agent"
                                               color: win.client.mode === modelData ? Theme.text : Theme.muted
                                               font.pixelSize: 12; font.weight: Font.DemiBold }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                    onClicked: win.client.setMode(parent.modelData) }
                                    }
                                }
                            }
                        }
                        Rectangle {
                            visible: win.client.mode === "agent"
                            Layout.fillWidth: true
                            implicitHeight: 30
                            radius: 9
                            color: Theme.surface
                            border.color: wsInput.activeFocus ? Theme.teal : Theme.border
                            TextInput {
                                id: wsInput
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                verticalAlignment: TextInput.AlignVCenter
                                text: win.client.workspace
                                onTextEdited: win.client.workspace = text
                                color: Theme.text
                                font.family: Theme.mono
                                font.pixelSize: 12
                                clip: true
                                Text { visible: wsInput.text === ""; anchors.verticalCenter: parent.verticalCenter
                                       text: "Workspace, e.g. ~/src/my-app"; color: Theme.faint; font.pixelSize: 12 }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: Math.min(Math.max(input.implicitHeight + 24, 48), 160)
                        radius: 14
                        color: Theme.surface
                        border.color: input.activeFocus ? Theme.teal : Theme.border
                        Flickable {
                            id: inputFlick
                            anchors.left: parent.left
                            anchors.right: sendBtn.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.margins: 12
                            contentHeight: input.implicitHeight
                            clip: true
                            TextEdit {
                                id: input
                                width: inputFlick.width
                                wrapMode: TextEdit.Wrap
                                color: Theme.text
                                font.pixelSize: 14
                                focus: true
                                Text { visible: input.text === "" && !input.preeditText
                                       text: win.client.mode === "agent" ? "Describe the task…" : "Ask DevOS AI…"
                                       color: Theme.faint; font.pixelSize: 14 }
                                // Enter sends, Shift+Enter inserts a newline.
                                Keys.onReturnPressed: event => {
                                    if (event.modifiers & Qt.ShiftModifier) { event.accepted = false; return; }
                                    if (win.client.runningTask === "") { win.client.send(input.text); input.text = ""; }
                                }
                            }
                        }
                        DButton {
                            id: sendBtn
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: 8
                            small: true
                            label: win.client.runningTask !== "" ? "Stop" : "Send"
                            variant: win.client.runningTask !== "" ? "danger" : "primary"
                            onClicked: {
                                if (win.client.runningTask !== "") { win.client.cancel(); return; }
                                win.client.send(input.text);
                                input.text = "";
                            }
                        }
                    }
                }
            }
        }
    }
}
