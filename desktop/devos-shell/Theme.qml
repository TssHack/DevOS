pragma Singleton
import QtQuick
import Quickshell

// DevOS design tokens (same palette as the GRUB theme).
Singleton {
    readonly property color bg: Qt.rgba(0.043, 0.067, 0.106, 0.975)      // #0B111B
    readonly property color surface: "#121a27"
    readonly property color surfaceHigh: "#182233"
    readonly property color border: Qt.rgba(1, 1, 1, 0.08)
    readonly property color text: "#e6edf7"
    readonly property color muted: "#8a96ab"
    readonly property color faint: "#5c6880"
    readonly property color teal: "#2dd4bf"
    readonly property color violet: "#8b5cf6"
    readonly property color danger: "#f87171"
    readonly property color warning: "#fbbf24"
    readonly property color success: "#4ade80"
    readonly property string mono: "JetBrains Mono"
    readonly property string display: "Space Grotesk"
    readonly property int radius: 14
    readonly property int gap: 12
}
