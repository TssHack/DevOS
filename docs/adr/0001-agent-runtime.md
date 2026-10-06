# ADR 0001: Agent runtime for DevOS 0.1.0

- Status: **Accepted (native runtime)**; Hermes adapter **pending** the SRS §14.4 spike
- Date: 2026-10-06

## Context

SRS AGENT-002 names Hermes Agent as a candidate runtime, but DevOS must not
depend on it, and every runtime must run sandboxed with its own tools, memory
and network disabled, using devosd for model calls and tools (§14).

## Decision

DevOS 0.1.0 ships the **native runtime** (`ai/devos/runtime/native.py`): a
small loop that asks devosd to call the model and to run tools. It is the
default (`ai.runtime = "native"`) and is covered by the end-to-end tests.

Hermes is integrated only if it passes all seven criteria of SRS §14.4. The
spike needs network access to fetch Hermes and a Gemini API key; it has not
been run yet. `ai.runtime = "hermes"` is rejected by devosd until an adapter
exists.

## Consequences

- No third-party agent code in the trusted path for 0.1.0.
- The runtime contract (agent.sock, [ipc.md](../ipc.md)) is the integration
  point for Hermes or any MCP-capable runtime later.
