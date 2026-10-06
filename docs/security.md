# DevOS AI security

How the controls in SRS §16–§18 are implemented, what is tested, and known gaps.

## Trust boundary

| Trusted | Untrusted |
|---|---|
| devosd, devos-pkg-helper, DevOS shell (UI) | the model and its output, agent runtimes, workspace contents, command output, network data |

## Controls and where they live

| Control | Implementation | Tests |
|---|---|---|
| Classification only from tool + canonical args + policy (PERM-002) | `ai/devos/policy.py` | `test_policy.py`: 298-case corpus (`ai/policy/corpus.txt`) |
| Denied paths, symlink escapes (§16.3, PERM-021) | canonical paths before checks; denied paths masked in every sandbox | `test_policy.py`, `test_sandbox.py` |
| Shells, wrappers (`env`, `timeout`, `xargs`, …) unwrapped; blocked programs inside `sh -c` scripts | `policy.py` | corpus |
| Sandbox: `/` read-only, workspace rw, no runtime dir (D-Bus, keyring, ssh/gpg agents, Wayland), scrubbed env, no network by default, PID/IPC/UTS namespaces, `no_new_privs`, time/memory/task limits | `ai/devos/sandbox.py` (bubblewrap + systemd scope) | `test_sandbox.py` (A-18) |
| Hardened git for read-only calls (`core.fsmonitor`, pager, external diff, hooks disabled) | `tools.py` `GIT_HARDENING` | |
| Approvals only on ui.sock; runtime sandboxed without home, network or ui.sock (ARCH-002..006) | `daemon.py` | `test_daemon.py` (A-19) |
| API key only in Secret Service, never in runtime, env, logs (AI-004) | `credentials.py`, provider proxy | `test_daemon.py` asserts the key never reaches requests or audit |
| Redaction of keys and tokens in audit/conversations (SEC-004) | `redact.py` | `test_checkpoints_audit.py` |
| Tool output marked untrusted, fixed system prompt (SEC-009) | `daemon.py` | `test_daemon.py` |
| Denied requests are not retried (RT-003); limits ask before continuing (AGENT-006) | `daemon.py` | `test_daemon.py` |
| Undo of every agent change (§17) | `checkpoints.py` | `test_checkpoints_audit.py`, `test_tools.py`, `test_daemon.py` |
| Only privileged path: `devos-pkg-helper` via polkit `auth_admin`, names only, protected packages (§16.5) | `ai/system/` | `test_pkg_helper.py` |
| Gemini base URL is not user-configurable (prevents redirecting the key) | `settings.py` | |

## Known gaps (tracked)

1. **Package signing (SEC-011).** The `[devos]` repository and ISO are not signed yet; the ISO uses `SigLevel = Optional TrustAll` for `[devos]`. Needs a DevOS packaging key.
2. **Podman inside the sandbox (SBX-002 exception).** Rootless Podman needs its runtime directory and user namespaces; agent `podman` commands currently run in the same sandbox and may fail. Needs a dedicated, reviewed exception.
3. **Prompt injection.** Mitigated (untrusted marking, fixed system prompt, approvals show the exact operation, sandbox still applies after approval), not solved. Approval fatigue remains a risk (T6).
4. **Security review (SEC-012)** has not happened yet.
