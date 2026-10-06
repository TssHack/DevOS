import QtQuick
import QtQuick.Layouts

// First-run Gemini setup with the data notice (SRS AI-003..005, FB-004).
ColumnLayout {
    id: root
    required property var client
    spacing: 14
    property string message: ""
    property bool working: false

    Text {
        text: "Connect Gemini"
        color: Theme.text
        font.family: Theme.display
        font.pixelSize: 22
        font.weight: Font.Bold
    }
    Text {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: Theme.muted
        font.pixelSize: 13
        lineHeight: 1.3
        text: "DevOS AI uses your own Google Gemini API key. It is stored in the system keyring, never in files or logs."
    }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: notice.implicitHeight + 24
        radius: 10
        color: Qt.rgba(0.98, 0.75, 0.14, 0.08)
        border.color: Qt.rgba(0.98, 0.75, 0.14, 0.3)
        Text {
            id: notice
            anchors.fill: parent
            anchors.margins: 12
            wrapMode: Text.WordWrap
            color: Theme.text
            font.pixelSize: 12
            lineHeight: 1.3
            text: "What is sent to Google: your messages, and in Agent mode the file contents and command output "
                + "the agent reads in that conversation. Nothing is sent until you send a message. "
                + "Google's terms for your API tier apply; on unpaid tiers Google may use this data to improve its products."
        }
    }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 40
        radius: 10
        color: Theme.surface
        border.color: keyInput.activeFocus ? Theme.teal : Theme.border
        TextInput {
            id: keyInput
            anchors.fill: parent
            anchors.margins: 12
            verticalAlignment: TextInput.AlignVCenter
            echoMode: TextInput.Password
            color: Theme.text
            font.family: Theme.mono
            font.pixelSize: 13
            clip: true
            focus: true
            Text {
                visible: keyInput.text === ""
                anchors.verticalCenter: parent.verticalCenter
                text: "Paste your Gemini API key"
                color: Theme.faint
                font.pixelSize: 13
            }
            onAccepted: save.clicked()
        }
    }
    RowLayout {
        DButton {
            id: save
            label: root.working ? "Testing…" : "Save and test"
            variant: "primary"
            onClicked: {
                if (root.working || keyInput.text.trim() === "") return;
                root.working = true;
                root.message = "";
                root.client.setKey(keyInput.text, (ok, err) => {
                    root.working = false;
                    keyInput.text = "";
                    root.message = ok ? "" : err;
                });
            }
        }
        Text {
            text: "Get a key at aistudio.google.com"
            color: Theme.faint
            font.pixelSize: 12
            Layout.leftMargin: 8
        }
    }
    Text {
        visible: root.message !== ""
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: root.message
        color: Theme.danger
        font.pixelSize: 12
    }
}
