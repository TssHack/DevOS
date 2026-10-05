<div align="center">

# DevOS

### The AI-Native Developer Operating System

**A developer-focused Linux distribution built on Arch Linux,
designed to make AI a first-class part of the operating system.**

<br>

[![Arch Linux](https://img.shields.io/badge/Base-Arch%20Linux-1793D1?style=for-the-badge\&logo=arch-linux\&logoColor=white)](https://archlinux.org/)
[![Hyprland](https://img.shields.io/badge/Desktop-Hyprland-58E6D9?style=for-the-badge)](https://hyprland.org/)
[![Gemini](https://img.shields.io/badge/AI-Gemini-4285F4?style=for-the-badge\&logo=google)](https://ai.google.dev/)
[![Status](https://img.shields.io/badge/Status-MVP%20Development-orange?style=for-the-badge)]()

<br>

> **AI should operate the system through DevOS, not around DevOS.**

</div>

---

## What is DevOS?

DevOS is an **AI-native Linux distribution for software developers**.

Built on top of Arch Linux, DevOS combines a modern Wayland desktop, a ready-to-use development environment, and an integrated AI agent capable of interacting with the operating system and development projects through a controlled permission system.

The goal is simple:

**Turn the operating system itself into a development companion.**

Instead of treating AI as another application running on top of the OS, DevOS makes AI part of the developer workflow.

---

## ✨ Core Ideas

<div align="center">

|             Developer First             |         AI Native         |         User Controlled        |
| :-------------------------------------: | :-----------------------: | :----------------------------: |
| Built around real development workflows | AI integrated into the OS | No unrestricted AI root access |

|               Modular              |        Reproducible        |          Open Source         |
| :--------------------------------: | :------------------------: | :--------------------------: |
| Replaceable providers and runtimes | Configuration lives in Git | Built with open technologies |

</div>

---

## 🧠 AI-Native Architecture

DevOS introduces a controlled bridge between AI and the operating system:

```text
                         ┌──────────────────┐
                         │      User        │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │    DevOS AI      │
                         │       UI         │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │      Agent       │
                         └────────┬─────────┘
                                  │
                                  ▼
                     ┌────────────────────────┐
                     │   Permission Manager   │
                     └────────────┬───────────┘
                                  │
                     ┌────────────┼────────────┐
                     ▼            ▼            ▼
                 Filesystem    Terminal       Git
                     │            │            │
                     └────────────┼────────────┘
                                  ▼
                              Linux OS
```

The AI does not directly control the system.

It requests operations.

**DevOS decides what is allowed.**

---

## 🤖 AI Capabilities

The DevOS agent is designed to work directly with development environments.

It can eventually:

* Inspect projects
* Understand project structure
* Read source code
* Search files
* Analyze errors
* Inspect Git state
* Run development commands
* Run tests
* Propose code changes
* Modify files with approval
* Inspect system resources
* Manage development environments

Potentially dangerous operations require explicit user approval.

```text
AI
 │
 ├── Read project
 ├── Analyze code
 ├── Inspect Git
 ├── Run command ──────► Approval
 │                         │
 │                         ▼
 │                      Execute
 │
 └── Modify system ────► Approval
```

---

## 🛡️ Security Model

DevOS follows a fundamental rule:

<div align="center">

# AI ≠ Root

</div>

Agent operations are classified into three levels:

### SAFE

Operations that normally require no confirmation.

```text
pwd
ls
git status
git diff
read_file
system_info
```

### CONFIRM

Operations that require explicit user approval.

```text
write_file
git commit
package installation
package removal
process termination
configuration changes
```

### BLOCKED

Operations that are blocked by default.

```text
disk formatting
destructive disk operations
credential extraction
security bypass
unrestricted privileged shell
```

The permission layer is independent from the AI provider.

---

## 🖥️ Developer Environment

DevOS aims to provide a complete development environment from the first boot.

### Languages & Toolchains

* C / C++
* Python
* JavaScript
* TypeScript
* Node.js
* Go
* Rust

### Development Tools

* Git
* OpenSSH
* GCC
* Clang
* CMake
* Make
* GDB
* Neovim
* Docker / Podman
* ripgrep
* fd
* fzf
* jq
* tmux
* curl
* wget

Developer profiles will allow users to install environments based on their workflow:

```text
General
Web
Backend
Systems
AI
Embedded
```

---

## 🖥️ Desktop

DevOS uses a modern Wayland-based desktop experience.

```text
Arch Linux
    │
    ├── Wayland
    │
    ├── Hyprland
    │
    └── end-4
```

The desktop is designed around:

* Keyboard-driven workflows
* Developer productivity
* Minimal distractions
* Modern UI
* Fast application access
* Integrated AI interaction

---

## 🏗️ Project Architecture

```text
devos/
│
├── iso/
├── core/
├── desktop/
├── developer/
├── ai/
│   ├── client/
│   ├── providers/
│   │   └── gemini/
│   ├── agent/
│   ├── runtime/
│   ├── tools/
│   └── permissions/
│
├── installer/
├── scripts/
└── docs/
```

The architecture is intentionally modular.

AI providers, agent runtimes, tools, and permission mechanisms should be replaceable without redesigning the entire operating system.

---

## 🚀 MVP

DevOS is currently in **MVP development**.

### Phase 1

```text
01  Foundation
        ↓
02  Desktop
        ↓
03  Developer Environment
        ↓
04  AI Client
        ↓
05  Agent Runtime
        ↓
06  Permission System
        ↓
07  Full Integration
        ↓
08  DevOS 0.1.0
```

The first release focuses on proving the core concept:

> **A developer can use an AI agent to interact with their development environment while DevOS remains in control of system-level operations.**

---

## 🧪 Example Workflow

A typical DevOS workflow:

```text
Boot DevOS
     ↓
Open Project
     ↓
Open DevOS AI
     ↓
Connect Gemini
     ↓
Ask Agent to Analyze Project
     ↓
Agent Inspects Files
     ↓
Agent Checks Git
     ↓
Agent Runs Tests
     ↓
Permission Request
     ↓
User Approval
     ↓
Agent Applies Fix
     ↓
Tests Run Again
     ↓
Task Complete
```

This workflow is the foundation of the DevOS vision.

---

## 🗺️ Roadmap

### MVP

* [x] Initial Archiso profile
* [ ] DevOS ISO build system
* [ ] Base system configuration
* [ ] Hyprland integration
* [ ] end-4 integration
* [ ] Developer environment
* [ ] AI client
* [ ] Gemini integration
* [ ] Agent runtime
* [ ] System tools
* [ ] Permission system
* [ ] MVP testing
* [ ] DevOS 0.1.0

### Future

* Local LLM support
* Multi-model support
* Multiple agent runtimes
* Agent skills
* Background agents
* Scheduled agents
* AI memory
* Voice interface
* Computer vision
* AI-assisted package management
* AI-assisted system administration
* Self-diagnosis
* Self-healing workflows

---

## 📚 Documentation

The project documentation is being developed alongside the implementation.

Important documents:

* **[Software Requirements Specification](SRS.md)**
* **[Roadmap](ROADMAP.md)**
* **[Contributing Guide](CONTRIBUTING.md)**

The SRS is the current architectural and functional baseline for MVP development.

---

## 🤝 Contributing

DevOS is being developed as an open-source project.

Contributions, ideas, experiments, documentation, testing, and architectural discussions are welcome.

Before contributing, please read:

```text
CONTRIBUTING.md
```

For major architectural changes, please discuss the proposal before implementation.

---

## 👨‍💻 Developer

<div align="center">

### Ehsan Fazli

Software Engineer · Computer Engineering · Linux · AI · Systems

**Building DevOS**

</div>

---

## 📜 License

License information will be finalized before the first public release.

---

<div align="center">

### DevOS

**Build. Think. Automate.**

<br>

*An operating system designed for the age of AI.*

</div>
