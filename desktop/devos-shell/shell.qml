//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

// DevOS desktop shell additions, one Quickshell process (started by Hyprland):
//   - DevOS AI panel (SRS AI-001)      keybind: hl.dsp.global("devos:aiToggle")
//   - first-login Welcome (SRS §7.2)   reopen:  qs -p /usr/share/devos/shell ipc call devos welcome
ShellRoot {
    DevosClient { id: client }

    AiPanel {
        id: panel
        client: client
    }

    StatusPill {
        client: client
        panel: panel
    }

    Welcome {
        id: welcome
        client: client
        onOpenAiPanel: panel.open = true
    }

    // Keybind target: hl.dsp.global("devos:aiToggle") — no process spawn per keypress.
    GlobalShortcut {
        appid: "devos"
        name: "aiToggle"
        description: "Toggle the DevOS AI panel"
        onPressed: panel.open = !panel.open
    }

    IpcHandler {
        target: "devos-ai"
        function toggle(): void { panel.open = !panel.open; }
        function open(): void { panel.open = true; }
        function close(): void { panel.open = false; }
        // For the bar indicator: off | idle | thinking | running | waiting | error
        function status(): string { return client.status; }
    }

    IpcHandler {
        target: "devos"
        function welcome(): void { welcome.show(); }
    }
}
