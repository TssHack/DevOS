import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Services.Greetd

// DevOS login screen: clock, user card, password, power actions.
// Authentication goes through greetd (PAM); the password is only passed to
// Greetd.respond() and never stored.
Item {
    id: root

    readonly property string lastUserFile: "/var/cache/devos-greeter/last-user"
    property string userName: ""
    property string message: ""
    property bool messageIsError: false
    property bool busy: false
    property string pendingPassword: ""
    property string hostName: ""

    // ------------------------------------------------------------ greetd flow
    function login() {
        if (busy) return;
        const u = userField.text.trim();
        if (u === "") { userField.forceActiveFocus(); return; }
        if (!Greetd.available) { showError("Login service is not available."); return; }
        busy = true;
        message = "";
        pendingPassword = passwordField.text;
        Greetd.createSession(u);
    }
    function showError(text) {
        message = text;
        messageIsError = true;
        busy = false;
        passwordField.text = "";
        pendingPassword = "";
        passwordField.forceActiveFocus();
        shake.restart();
    }

    Connections {
        target: Greetd
        function onAuthMessage(text, error, responseRequired, echoResponse) {
            if (error) { showError(text); return; }
            if (responseRequired) {
                // Password prompt (hidden input). Visible prompts get the user name.
                Greetd.respond(echoResponse ? userField.text.trim() : root.pendingPassword);
                root.pendingPassword = "";
            } else if (text !== "") {
                root.message = text;
                root.messageIsError = false;
            }
        }
        function onAuthFailure(text) {
            // greetd has already ended this session; the next attempt starts a new one.
            showError("Wrong password. Try again.");
        }
        function onError(text) {
            console.warn("greetd:", text);
            if (root.messageIsError && root.message !== "") return;  // keep the clearer message
            showError("Login failed. Try again.");
        }
        function onReadyToLaunch() {
            lastUser.setText(userField.text.trim());
            root.message = "Starting DevOS…";
            root.messageIsError = false;
            Greetd.launch(["devos-session"], [], true);
        }
    }

    // ------------------------------------------------- user name, host name
    FileView {
        id: lastUser
        path: root.lastUserFile
        onLoaded: { const t = text().trim(); if (t !== "") userField.text = t; root.focusInitial(); }
        // Nobody has logged in yet: fall back to the first regular user.
        onLoadFailed: passwd.path = "/etc/passwd"
    }
    FileView {
        id: passwd
        // First regular user (uid 1000-59999) when no one has logged in yet.
        onLoaded: {
            for (const line of text().split("\n")) {
                const f = line.split(":");
                const uid = parseInt(f[2]);
                if (uid >= 1000 && uid < 60000 && !(f[6] || "").endsWith("nologin")) {
                    if (userField.text === "") userField.text = f[0];
                    break;
                }
            }
            root.focusInitial();
        }
    }
    FileView { path: "/etc/hostname"; onLoaded: root.hostName = text().trim() }
    function focusInitial() {
        if (userField.text !== "") passwordField.forceActiveFocus(); else userField.forceActiveFocus();
    }

    // --------------------------------------------------------------- visuals
    Image {
        anchors.fill: parent
        source: "background.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
    }

    SystemClock { id: clock; precision: SystemClock.Minutes }

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: parent.height * 0.12
        spacing: 2
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Qt.formatTime(clock.date, "HH:mm")
            color: Theme.text
            font.family: Theme.display
            font.pixelSize: 96
            font.weight: Font.Bold
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Qt.formatDate(clock.date, "dddd, d MMMM")
            color: Theme.muted
            font.pixelSize: 20
        }
    }

    // Login card
    Rectangle {
        id: card
        anchors.centerIn: parent
        anchors.verticalCenterOffset: parent.height * 0.08
        width: 400
        height: cardCol.implicitHeight + 56
        radius: 24
        color: Qt.rgba(0.043, 0.067, 0.106, 0.72)
        border.color: Qt.rgba(1, 1, 1, 0.09)

        SequentialAnimation {
            id: shake
            NumberAnimation { target: card; property: "anchors.horizontalCenterOffset"; to: -10; duration: 50 }
            NumberAnimation { target: card; property: "anchors.horizontalCenterOffset"; to: 10; duration: 70 }
            NumberAnimation { target: card; property: "anchors.horizontalCenterOffset"; to: -6; duration: 60 }
            NumberAnimation { target: card; property: "anchors.horizontalCenterOffset"; to: 0; duration: 50 }
        }

        ColumnLayout {
            id: cardCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 28
            spacing: 14

            // Avatar: user initial on the DevOS accent gradient
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 84; height: 84; radius: 42
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Theme.teal }
                    GradientStop { position: 1; color: Theme.violet }
                }
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 3
                    radius: width / 2
                    color: "#0e1521"
                    Text {
                        anchors.centerIn: parent
                        text: userField.text !== "" ? userField.text[0].toUpperCase() : "›_"
                        color: Theme.text
                        font.family: Theme.display
                        font.pixelSize: 34
                        font.weight: Font.Bold
                    }
                }
            }

            // User name
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 46
                radius: 12
                color: Qt.rgba(1, 1, 1, 0.05)
                border.color: userField.activeFocus ? Theme.teal : Qt.rgba(1, 1, 1, 0.10)
                TextInput {
                    id: userField
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    verticalAlignment: TextInput.AlignVCenter
                    horizontalAlignment: TextInput.AlignHCenter
                    color: Theme.text
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                    clip: true
                    enabled: !root.busy
                    KeyNavigation.tab: passwordField
                    onAccepted: passwordField.forceActiveFocus()
                    Text {
                        visible: userField.text === ""
                        anchors.centerIn: parent
                        text: "User name"
                        color: Theme.faint
                        font.pixelSize: 16
                    }
                }
            }

            // Password
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 46
                radius: 12
                color: Qt.rgba(1, 1, 1, 0.05)
                border.color: root.messageIsError && root.message !== "" ? Theme.danger
                            : passwordField.activeFocus ? Theme.teal : Qt.rgba(1, 1, 1, 0.10)
                TextInput {
                    id: passwordField
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 52
                    verticalAlignment: TextInput.AlignVCenter
                    echoMode: TextInput.Password
                    passwordCharacter: "•"
                    color: Theme.text
                    font.pixelSize: 17
                    clip: true
                    enabled: !root.busy
                    KeyNavigation.tab: userField
                    onAccepted: root.login()
                    onTextEdited: if (root.messageIsError) root.message = ""
                    Text {
                        visible: passwordField.text === ""
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Password"
                        color: Theme.faint
                        font.pixelSize: 16
                    }
                }
                // Submit arrow
                Rectangle {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.rightMargin: 6
                    width: 34; height: 34; radius: 10
                    color: arrow.containsMouse ? "#3ee0cb" : Theme.teal
                    opacity: root.busy ? 0.5 : 1
                    Text { anchors.centerIn: parent; text: root.busy ? "…" : "→"; color: "#06231f"
                           font.pixelSize: 18; font.weight: Font.Bold }
                    MouseArea { id: arrow; anchors.fill: parent; hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor; onClicked: root.login() }
                }
            }

            Text {
                Layout.fillWidth: true
                Layout.minimumHeight: 18
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: root.message
                color: root.messageIsError ? Theme.danger : Theme.muted
                font.pixelSize: 13
            }
        }
    }

    // Brand, bottom-left
    RowLayout {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 28
        spacing: 10
        Rectangle {
            width: 30; height: 30; radius: 9
            color: "#0e1521"
            border.width: 1.5
            border.color: Theme.teal
            Text { anchors.centerIn: parent; text: "›_"; color: Theme.teal
                   font.family: Theme.mono; font.pixelSize: 13; font.weight: Font.Bold }
        }
        Text { text: "DevOS"; color: Theme.text; font.family: Theme.display; font.pixelSize: 17; font.weight: Font.Bold }
        Text { text: root.hostName; color: Theme.faint; font.pixelSize: 13; Layout.leftMargin: 6 }
    }

    // Power, bottom-right
    Process { id: power }
    RowLayout {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 24
        spacing: 8
        DButton { label: "Restart"; variant: "ghost"; small: true
                  onClicked: { power.command = ["systemctl", "reboot"]; power.running = true; } }
        DButton { label: "Power off"; variant: "ghost"; small: true
                  onClicked: { power.command = ["systemctl", "poweroff"]; power.running = true; } }
    }
}
