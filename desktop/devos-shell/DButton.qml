import QtQuick

// Button with a visible keyboard focus ring. Activates on click, or on
// Enter/Space only while it has focus (SRS UX-001).
Rectangle {
    id: b
    property string label: ""
    property string variant: "secondary"   // primary | secondary | danger | ghost
    property bool small: false
    signal clicked()

    activeFocusOnTab: true
    implicitHeight: small ? 28 : 36
    implicitWidth: txt.implicitWidth + (small ? 20 : 28)
    radius: small ? 8 : 10
    color: variant === "primary" ? (mouse.containsMouse ? "#3ee0cb" : Theme.teal)
         : variant === "danger" ? (mouse.containsMouse ? Qt.rgba(0.97, 0.44, 0.44, 0.22) : Qt.rgba(0.97, 0.44, 0.44, 0.12))
         : variant === "ghost" ? (mouse.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent")
         : (mouse.containsMouse ? Theme.surfaceHigh : Theme.surface)
    border.width: activeFocus ? 2 : 1
    border.color: activeFocus ? Theme.text
                : variant === "danger" ? Qt.rgba(0.97, 0.44, 0.44, 0.4)
                : variant === "primary" ? "transparent" : Theme.border

    Text {
        id: txt
        anchors.centerIn: parent
        text: b.label
        color: b.variant === "primary" ? "#06231f" : b.variant === "danger" ? Theme.danger : Theme.text
        font.pixelSize: b.small ? 12 : 13
        font.weight: Font.DemiBold
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: b.clicked()
    }
    Keys.onReturnPressed: b.clicked()
    Keys.onEnterPressed: b.clicked()
    Keys.onSpacePressed: b.clicked()
}
