# devosd IPC protocol

SRS ARCH-005..007. Protocol version **1**.

## Transport

- JSON-RPC 2.0, one JSON object per line, over Unix stream sockets.
- `$XDG_RUNTIME_DIR/devos/ui.sock` (directory `0700`, socket `0600`): UI clients (DevOS shell, `devos` CLI).
- `$XDG_RUNTIME_DIR/devos/agent/agent.sock`: agent runtimes only. This directory is the only one bind-mounted into the runtime sandbox.
- Connections from other UIDs are closed (`SO_PEERCRED`).
- Requests on one connection run concurrently; long calls (`chat.send`, `agent.run`) resolve when finished while events stream as notifications.

## ui.sock methods

| Method | Params | Result |
|---|---|---|
| `hello` | `protocol` | `protocol, version, provider, model, key, settings_error` |
| `events.subscribe` | — | `pending_approvals` (receive the events below from now on) |
| `key.set` | `key` | `storage`: `keyring` \| `memory` |
| `key.test` | — | `ok`, or `ok:false, kind, message` |
| `key.remove`, `key.status` | — | |
| `models.list` | — | `models, current` |
| `settings.get` | — | `settings, error, limits, runtimes` |
| `settings.set` | `section, key, value` | user-settable: `ai.model`, `ai.runtime`, `daemon.*`, `env.<NAME>` |
| `settings.unset_env` | `key` | |
| `conv.list` / `conv.get` / `conv.create` / `conv.rename` / `conv.delete` | | conversations (AI-008) |
| `conv.set_mode` | `id, mode, workspace?` | chat ↔ agent (AI-009) |
| `chat.send` | `conv, text` | `message` (after streaming) |
| `agent.run` | `conv, text` | task summary (after the task ends) |
| `approval.respond` | `id, decision`: `once` \| `session` \| `deny` | **only accepted on ui.sock** |
| `task.cancel` | `task` | |
| `task.undo` | `task, force?` | `status: ok, restored, removed` or `status: conflict, files` |
| `audit.tail` | `n` | `records` |
| `data.reset` | — | deletes conversations, audit, checkpoints, key (STOR-001) |

## ui.sock events

| Event | Params |
|---|---|
| `chat.delta`, `agent.text` | `conv`/`task`, `text` (streamed model text) |
| `chat.done`, `chat.error` | `conv, message` / `conv, kind, message` |
| `provider.busy` | `busy, provider` (PRIV-012 indicator) |
| `agent.started` | `task, conv, workspace` |
| `agent.tool` | `task, rid, tool, preview, level, reason, state` (`running`, `done`, `failed`, `denied`, `blocked`) |
| `approval.request` | `id, kind` (`tool` \| `continue`), `tool, preview, level, reason, undoable` |
| `approval.closed` | `id` |
| `agent.done` | `task, status, text, files_changed, commands, tool_calls, sent_files, undo_available` |

`preview` holds exactly what will run: `argv`, `cwd`, `network`, `timeout_s` for commands, `path` and `diff` for file changes, `packages` for package changes (PERM-003).

## agent.sock methods

| Method | Notes |
|---|---|
| `task.attach` | `token` from the runtime's environment; one connection per task |
| `task.get` | conversation messages and the tool list (MCP-style `name, description, inputSchema`) |
| `model.stream` | `messages` → final model message. devosd adds the system prompt and tools and holds the API key (ARCH-003) |
| `tools.call` | `name, args, id` → result wrapped as `{status, note, untrusted_output}` (SEC-009) |
| `status` | `text` for the activity view |
| `task.finish` | `text`: the final answer |

There is no method on agent.sock that approves, changes or reads permissions.
