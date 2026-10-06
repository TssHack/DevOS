import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

// DevOS AI activity indicator (SRS DESK-008, §20.3): visible only while the AI is
// active (thinking / running / waiting) and the panel is closed. Click opens the panel.
PanelWindow {
    id: pill
    required property var client
    required property var panel
    readonly property bool active: ["thinking", "running", "waiting"].includes(client.status)

    visible: active && !panel.open
    anchors { top: true; right: true }
    margins { top: 8; right: 12 }
    implicitWidth: row.implicitWidth + 24
    implicitHeight: 32
    exclusiveZone: 0
    color: "transparent"
    WlrLayershell.namespace: "devos-ai-status"
    WlrLayershell.layer: WlrLayer.Overlay

    Rectangle {
        anchors.fill: parent
        radius: 16
        color: pill.client.status === "waiting" ? Qt.rgba(0.98, 0.75, 0.14, 0.95) : Theme.bg
        border.color: pill.client.status === "waiting" ? "transparent" : Theme.border
        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 8
            Rectangle {
                width: 8; height: 8; radius: 4
                color: pill.client.status === "waiting" ? "#3a2a00"
                     : pill.client.status === "thinking" ? Theme.violet : Theme.teal
                SequentialAnimation on opacity {
                    running: pill.visible
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.3; duration: 500 }
                    NumberAnimation { to: 1; duration: 500 }
                }
            }
            Text {
                text: pill.client.status === "waiting" ? "DevOS AI needs your approval"
                    : pill.client.status === "thinking" ? "DevOS AI · sending to Gemini" : "DevOS AI · running"
                color: pill.client.status === "waiting" ? "#3a2a00" : Theme.text
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: pill.panel.open = true }
    }
}
