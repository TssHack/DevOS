# DevOS AI

The trusted AI layer of DevOS (SRS §10–§19). Pure Python standard library, no
third-party dependencies.

| Path | What |
|---|---|
| `devos/daemon.py` | **devosd**: UI and agent sockets, permission flow, approvals, provider proxy, tasks |
| `devos/policy.py` | Permission Manager: path scopes and command classification (§16) |
| `devos/sandbox.py` | bubblewrap sandbox for every agent process (§16.4) |
| `devos/tools.py` | Tool registry and implementations (§15) |
| `devos/checkpoints.py` | Per-task checkpoints and undo (§17) |
| `devos/audit.py`, `redact.py` | Audit log and secret redaction (§19, SEC-004) |
| `devos/credentials.py` | API key in the Secret Service (AI-004) |
| `devos/providers/gemini.py` | Gemini REST provider with streaming and retries (§13) |
| `devos/runtime/native.py` | Native agent runtime, runs sandboxed (§14) |
| `devos/rpc.py` | JSON-RPC 2.0 over Unix sockets ([docs/ipc.md](../docs/ipc.md)) |
| `devos/cli.py` | `devos` command line |
| `policy/` | Default policy, defaults, classifier corpus (PERM-014) |
| `system/` | `devos-pkg-helper`, polkit action, systemd user units |
| `tests/` | Unit and end-to-end tests |

The graphical panel is in [desktop/devos-shell](../desktop/devos-shell); the
package is [packaging/devos-ai](../packaging/devos-ai/PKGBUILD).

## Develop

```bash
cd ai
PYTHONPATH=.:tests python -m unittest discover -s tests     # all tests
DEVOS_SOURCE_TREE=1 PYTHONPATH=. python -m devos.daemon    # run devosd from the tree
PYTHONPATH=. python -m devos.cli ai status                 # talk to it
```

Tests that start real sandboxes need bubblewrap; they skip themselves where it
cannot run (some build chroots).
