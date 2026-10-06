import QtQuick
import Quickshell
import Quickshell.Io

// JSON-RPC client for devosd over $XDG_RUNTIME_DIR/devos/ui.sock (SRS ARCH-007).
// Holds the conversation shown in the panel. Presentation only: no secrets are
// kept here and every permission decision is made by devosd.
Item {
    id: client

    property bool connected: sock.connected
    property string keyStatus: "unknown"       // keyring | memory | missing
    property string model: ""
    property bool providerBusy: false
    property string runningTask: ""
    property bool toolRunning: false
    property string convId: ""
    property string mode: "chat"               // chat | agent
    property string workspace: ""
    property int approvalCount: 0
    property string lastError: ""
    // off | idle | thinking | running | waiting | error   (SRS §20.3)
    readonly property string status: !connected || keyStatus === "missing" ? "off"
        : approvalCount > 0 ? "waiting"
        : providerBusy ? "thinking"
        : toolRunning ? "running"
        : lastError !== "" ? "error" : "idle"

    property ListModel items: ListModel {}
    property ListModel conversations: ListModel {}
    property var _pending: ({})
    property int _nextId: 1

    Socket {
        id: sock
        path: Quickshell.env("XDG_RUNTIME_DIR") + "/devos/ui.sock"
        parser: SplitParser { onRead: line => client._onLine(line) }
        onConnectedChanged: {
            if (connected) {
                reconnect.interval = 1000;
                client._handshake();
            } else {
                client._failPending("devosd disconnected");
                client.runningTask = "";
                client.providerBusy = false;
                client.toolRunning = false;
                client.approvalCount = 0;
                reconnect.start();
            }
        }
        onError: reconnect.start()
    }

    // Reconnect with backoff (1 s .. 30 s). Socket activation restarts devosd.
    Timer {
        id: reconnect
        interval: 1000
        onTriggered: {
            if (sock.connected) return;
            sock.connected = true;
            interval = Math.min(interval * 2, 30000);
        }
    }

    // devosd is socket-activated and exits when idle; reconnect on demand.
    function ensureConnected() {
        if (!sock.connected) sock.connected = true;
    }

    function call(method, params, cb) {
        ensureConnected();
        const id = _nextId++;
        if (cb) _pending[id] = cb;
        sock.write(JSON.stringify({ jsonrpc: "2.0", id: id, method: method, params: params || {} }) + "\n");
        sock.flush();
    }

    function _onLine(line) {
        let msg;
        try { msg = JSON.parse(line); } catch (e) { return; }
        if (msg.id !== undefined && msg.id !== null) {
            const cb = _pending[msg.id];
            delete _pending[msg.id];
            if (cb) cb(msg.error ? null : msg.result, msg.error ? msg.error.message : "");
        } else if (msg.method) {
            _onEvent(msg.method, msg.params || {});
        }
    }

    function _failPending(reason) {
        const p = _pending;
        _pending = {};
        for (const id in p) p[id](null, reason);
    }

    function _handshake() {
        call("hello", { protocol: 1 }, (r, err) => {
            if (!r) { lastError = err; return; }
            keyStatus = r.key;
            model = r.model;
            call("events.subscribe", {}, s => {
                if (s) s.pending_approvals.forEach(a => _addApproval(a));
            });
        });
    }

    // ------------------------------------------------------------ items
    function _blank() {
        return { kind: "", text: "", tool: "", detail: "", state: "", rid: "", approvalId: "", diff: "",
                 reason: "", undoable: true, resolved: false, allowSession: false, task: "", files: "",
                 approvalKind: "" };
    }
    function _add(fields) {
        const o = _blank();
        for (const k in fields) o[k] = fields[k];
        items.append(o);
    }
    function _appendModelText(t) {
        const n = items.count;
        if (n > 0 && items.get(n - 1).kind === "model" && items.get(n - 1).state === "streaming")
            items.setProperty(n - 1, "text", items.get(n - 1).text + t);
        else
            _add({ kind: "model", text: t, state: "streaming" });
    }
    function _closeModelText() {
        const n = items.count;
        if (n > 0 && items.get(n - 1).kind === "model") items.setProperty(n - 1, "state", "done");
    }
    function _toolDetail(p) {
        const v = p.preview || {};
        if (v.argv) return v.argv.join(" ");
        if (v.packages) return v.action + " " + v.packages.join(" ");
        if (v.path) return shortHome(v.path);
        if (v.query) return v.query;
        return "";
    }
    function _addApproval(a) {
        _closeModelText();
        const v = a.preview || {};
        let detail = _toolDetail(a);
        if (v.cwd) detail += "\nin " + shortHome(v.cwd) + "\nnetwork " + (v.network ? "ON" : "off");
        _add({ kind: "approval", approvalId: a.id, approvalKind: a.kind, tool: a.tool || "",
               detail: a.kind === "continue" ? "" : detail, reason: a.reason || "", diff: v.diff || "",
               undoable: a.undoable !== false, allowSession: a.tool === "execute_command" });
        approvalCount++;
    }

    function _onEvent(method, p) {
        switch (method) {
        case "chat.delta":
        case "agent.text":
            _appendModelText(p.text);
            break;
        case "chat.done":
            _closeModelText();
            break;
        case "chat.error":
            _closeModelText();
            lastError = p.message;
            _add({ kind: "error", text: p.message });
            break;
        case "provider.busy":
            providerBusy = p.busy;
            if (p.busy) lastError = "";
            break;
        case "agent.started":
            runningTask = p.task;
            break;
        case "agent.tool": {
            _closeModelText();
            toolRunning = p.state === "running";
            for (let i = items.count - 1; i >= 0; i--) {
                if (items.get(i).rid === p.rid) { items.setProperty(i, "state", p.state); return; }
            }
            _add({ kind: "tool", rid: p.rid, tool: p.tool, detail: _toolDetail(p), state: p.state,
                   reason: p.state === "blocked" ? p.reason : "" });
            break;
        }
        case "approval.request":
            _addApproval(p);
            break;
        case "approval.closed":
            for (let i = 0; i < items.count; i++) {
                if (items.get(i).approvalId === p.id && !items.get(i).resolved) {
                    items.setProperty(i, "resolved", true);
                    approvalCount = Math.max(0, approvalCount - 1);
                }
            }
            break;
        case "agent.done":
            _closeModelText();
            runningTask = "";
            toolRunning = false;
            _add({ kind: "summary", task: p.task, state: p.status, text: p.text || "",
                   files: (p.files_changed || []).join(", "),
                   detail: (p.sent_files || []).length ? "Sent to Gemini: " + p.sent_files.join(", ") : "",
                   undoable: p.undo_available });
            break;
        }
    }

    // ------------------------------------------------------------ actions
    function send(text) {
        if (text.trim() === "") return;
        lastError = "";
        if (convId === "") {
            const params = { mode: mode };
            if (mode === "agent") params.workspace = expandHome(workspace);
            call("conv.create", params, (c, err) => {
                if (!c) { _add({ kind: "error", text: err }); return; }
                convId = c.id;
                _send(text);
            });
        } else {
            _send(text);
        }
    }
    function _send(text) {
        _add({ kind: "user", text: text });
        const method = mode === "agent" ? "agent.run" : "chat.send";
        call(method, { conv: convId, text: text }, (r, err) => {
            if (!r && err) { lastError = err; _add({ kind: "error", text: err }); }
        });
    }
    function setMode(m) {
        if (m === mode) return;
        if (convId !== "" && m === "agent" && workspace === "") { mode = m; return; }
        mode = m;
        if (convId !== "")
            call("conv.set_mode", { id: convId, mode: m, workspace: m === "agent" ? expandHome(workspace) : "" },
                 (r, err) => { if (!r) _add({ kind: "error", text: err }); });
    }
    function respond(approvalId, decision) {
        call("approval.respond", { id: approvalId, decision: decision });
    }
    function cancel() {
        if (runningTask !== "") call("task.cancel", { task: runningTask });
    }
    function undo(task, force) {
        call("task.undo", { task: task, force: !!force }, (r, err) => {
            if (!r) { _add({ kind: "error", text: err }); return; }
            if (r.status === "conflict")
                _add({ kind: "error", text: "Changed after the task: " + r.files.join(", ") + ". Undo again to overwrite.",
                       task: task, state: "conflict" });
            else
                _add({ kind: "info", text: "Undone: restored " + r.restored.length + ", removed " + r.removed.length + " file(s)." });
        });
    }
    function newConversation() {
        if (runningTask !== "") return;
        convId = "";
        items.clear();
        approvalCount = 0;
    }
    function loadConversations() {
        call("conv.list", {}, r => {
            conversations.clear();
            if (r) r.conversations.forEach(c => conversations.append(
                { id: c.id, title: c.title, mode: c.mode, workspace: c.workspace || "" }));
        });
    }
    function openConversation(id) {
        call("conv.get", { id: id }, c => {
            if (!c) return;
            items.clear();
            convId = c.id;
            mode = c.mode;
            workspace = c.workspace || workspace;
            c.messages.forEach(m => {
                if (m.role === "user") _add({ kind: "user", text: m.text });
                else if (m.role === "model" && m.text) _add({ kind: "model", text: m.text, state: "done" });
            });
        });
    }
    function deleteConversation(id) {
        call("conv.delete", { id: id }, () => {
            if (id === convId) newConversation();
            loadConversations();
        });
    }
    function setKey(key, cb) {
        call("key.set", { key: key }, (r, err) => {
            if (!r) { cb(false, err); return; }
            call("key.test", {}, t => {
                keyStatus = t && t.ok ? r.storage : keyStatus;
                cb(t && t.ok, t ? (t.ok ? "" : t.message) : "devosd did not answer");
            });
        });
    }
    function shortHome(p) {
        const h = Quickshell.env("HOME");
        return p === h ? "~" : p.startsWith(h + "/") ? "~" + p.slice(h.length) : p;
    }
    function expandHome(p) {
        return p.startsWith("~") ? Quickshell.env("HOME") + p.slice(1) : p;
    }

    Component.onCompleted: ensureConnected()
}
