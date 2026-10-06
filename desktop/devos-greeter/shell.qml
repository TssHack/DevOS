//@ pragma UseQApplication
import QtQuick
import Quickshell

// DevOS graphical login (SRS DESK-010). Runs as the greetd greeter inside cage:
//   cage -s -- qs -p /usr/share/devos/greeter
ShellRoot {
    FloatingWindow {
        title: "DevOS Login"
        color: "#070a11"
        LoginScreen { anchors.fill: parent }
    }
}
