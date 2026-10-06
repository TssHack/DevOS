import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

// First-login Welcome (SRS §7.2, FB-001..005): developer profiles and AI setup.
// Shown once; reopen from the launcher ("DevOS Welcome").
FloatingWindow {
    id: win
    required property var client
    signal openAiPanel()

    readonly property string markerPath: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state")
                                         + "/devos/welcome-done"
    readonly property var profiles: [
        { id: "web", title: "Web", desc: "pnpm, Bun, Deno, nginx, browsers for testing" },
        { id: "backend", title: "Backend", desc: "PostgreSQL, Valkey, JDK, .NET, PHP, gRPC" },
        { id: "systems", title: "Systems", desc: "LLVM, QEMU, bpftrace, meson, mold" },
        { id: "ai", title: "AI / data", desc: "PyTorch, NumPy, pandas, Jupyter" },
        { id: "embedded", title: "Embedded", desc: "ARM and AVR toolchains, OpenOCD" },
    ]
    property var installed: ({})
    property var selected: ({})

    title: "Welcome to DevOS"
    implicitWidth: 760
    implicitHeight: 620
    color: Theme.bg
    visible: false

    function show() { refreshInstalled(); visible = true; }
    function finish() {
        markDone.running = true;
        visible = false;
    }
    function refreshInstalled() { query.running = true; }

    // FB-005: shown once, unless reopened explicitly.
    Process {
        id: checkMarker
        command: ["test", "-e", win.markerPath]
        running: true
        onExited: code => { if (code !== 0) win.show(); }
    }
    Process {
        id: markDone
        command: ["sh", "-c", "mkdir -p \"$(dirname \"$1\")\" && touch \"$1\"", "sh", win.markerPath]
    }
    Process {
        id: query
        command: ["pacman", "-Qq", "devos-profile-general", "devos-profile-web", "devos-profile-backend",
                  "devos-profile-systems", "devos-profile-ai", "devos-profile-embedded"]
        property var found: ({})
        stdout: SplitParser { onRead: line => query.found[line.replace("devos-profile-", "")] = true }
        onRunningChanged: if (!running) { win.installed = query.found; query.found = {}; }
    }
    // FB-002: installs run in a terminal so progress and the password prompt are visible.
    Process { id: installer }

    function installSelected() {
        const pkgs = Object.keys(selected).filter(k => selected[k] && !installed[k]).map(k => "devos-profile-" + k);
        if (pkgs.length === 0) return;
        installer.command = ["kitty", "--title", "DevOS: installing profiles", "sh", "-c",
            "sudo pacman -S --needed " + pkgs.join(" ") + "; echo; read -p 'Press Enter to close' _"];
        installer.running = true;
    }

    WelcomeContent {
        anchors.fill: parent
        host: win
    }
}
