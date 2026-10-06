# DevOS

## Software Requirements Specification

**Project:** DevOS
**Document:** Software Requirements Specification (SRS)
**Version:** 0.1.0
**Status:** Draft / Pre-Development Baseline
**Phase:** MVP / Phase 1
**Base Distribution:** Arch Linux
**Target Architecture:** x86_64
**Primary Desktop:** Hyprland
**Desktop Shell / Configuration:** end-4
**Primary AI Provider:** Google Gemini API
**Primary Agent Runtime Candidate:** Hermes Agent
**Developer:** Ehsan Fazli
**GitHub Organization:** https://github.com/DevOS

---

# 1. Introduction

## 1.1 Purpose

This document defines the software requirements, architecture boundaries, functional requirements, non-functional requirements, security requirements, and acceptance criteria for **DevOS MVP v0.1**.

DevOS is a developer-focused Linux distribution built on top of Arch Linux.

The primary objective is to provide a modern operating system specifically designed for software developers while introducing an integrated AI layer capable of interacting with the user's development environment and, with explicit permission, performing system-level operations.

DevOS is not intended to be a simple Arch Linux remaster.

The project aims to establish a dedicated operating-system layer that integrates:

* Linux system infrastructure
* Developer tooling
* Modern Wayland desktop experience
* AI-assisted development
* System-level AI agents
* Permission-controlled tool execution

---

# 2. Project Vision

## 2.1 Vision Statement

> DevOS is an AI-native developer operating system designed to make software development a first-class operating-system experience.

The system should allow a developer to install the operating system, enter a ready-to-use development environment, open projects, and interact with an AI agent capable of understanding and operating within the development environment.

The AI should not merely answer questions.

It should be able to:

* inspect projects
* understand project structure
* read source code
* analyze errors
* execute development commands
* interact with Git
* inspect system resources
* manage development environments
* propose changes
* modify files with user approval
* execute approved operations

All potentially dangerous operations must remain under a permission and approval model controlled by the operating system.

---

# 3. Product Goals

## 3.1 Primary Goals

DevOS MVP shall provide:

1. A bootable Arch-based Linux distribution.
2. A modern Hyprland-based desktop.
3. end-4 as the initial desktop shell/configuration foundation.
4. A preconfigured developer environment.
5. Common programming languages and development tools.
6. An integrated AI interface.
7. Google Gemini API integration.
8. User-provided Gemini API credentials.
9. AI chat functionality.
10. Agent functionality.
11. System and development tool integration.
12. Permission-controlled agent execution.
13. A modular architecture for future AI providers and agent runtimes.

---

# 4. Product Philosophy

DevOS shall follow the following principles.

## 4.1 Developer First

The operating system must optimize for software development workflows.

## 4.2 AI Native

AI should be integrated into the operating-system experience rather than existing only as an independent web application.

## 4.3 User Controlled

The AI agent must never silently gain unrestricted control over the user's system.

## 4.4 Modular

Core components should be replaceable without requiring a complete redesign of the operating system.

## 4.5 Open Source Friendly

DevOS should prioritize open-source components whenever practical.

## 4.6 Reproducible

The operating system should be buildable from source-controlled configuration.

## 4.7 Minimal Unnecessary Complexity

The MVP should focus on delivering a functional developer operating system instead of attempting to solve every operating-system problem simultaneously.

---

# 5. Scope

## 5.1 In Scope

The MVP includes:

### Operating System

* Arch Linux base
* Linux kernel
* systemd
* pacman
* x86_64 support
* UEFI boot
* networking
* hardware firmware

### Desktop

* Wayland
* Hyprland
* end-4 environment
* terminal
* launcher
* notifications
* status bar
* desktop configuration
* basic theming

### Developer Environment

* Git
* SSH
* C/C++
* Python
* JavaScript
* TypeScript
* Node.js
* Go
* Rust
* build tools
* debugging tools
* terminal utilities
* editor
* container runtime

### AI

* AI desktop interface
* Gemini API
* user API key
* chat
* streaming responses
* conversation management
* agent mode
* tool calling
* filesystem access
* terminal access
* Git integration
* system information
* permission management

### Agent

* Agent runtime abstraction
* Hermes integration candidate
* tool system
* execution layer
* permission layer
* activity visibility

---

# 6. Out of Scope

The following are explicitly outside the MVP scope:

* custom Linux kernel
* custom package manager
* custom desktop environment
* custom AI model
* training an AI model
* local LLM
* multi-agent orchestration
* voice assistant
* AI vision system
* cloud synchronization
* user accounts
* mobile application
* enterprise device management
* application store
* cloud-hosted development environments
* automatic autonomous system administration
* unrestricted AI root access
* custom Secure Boot infrastructure
* immutable/atomic operating system architecture

These may be considered in future versions.

---

# 7. High-Level Architecture

```text
                         ┌───────────────────────────┐
                         │           DevOS           │
                         │ Developer + AI OS         │
                         └─────────────┬─────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
       ┌─────────────┐        ┌────────────────┐       ┌─────────────────┐
       │ Linux Core  │        │ Developer      │       │ AI Platform     │
       │             │        │ Environment    │       │                 │
       └──────┬──────┘        └───────┬────────┘       └────────┬────────┘
              │                       │                         │
              ▼                       ▼                         ▼
        Arch Linux              Dev Toolchain              AI Client
              │                       │                         │
              │                       │                  Provider Adapter
              │                       │                         │
              │                       │                      Gemini
              │                       │                         │
              │                       │                   Agent Runtime
              │                       │                         │
              │                       │                 ┌───────┴────────┐
              │                       │                 │ Hermes Adapter │
              │                       │                 └───────┬────────┘
              │                       │                         │
              └───────────────────────┼─────────────────────────┘
                                      │
                              Permission Layer
                                      │
                                Tool Executor
                                      │
             ┌────────────────────────┼────────────────────────┐
             │                        │                        │
         Filesystem                Terminal                  Git
             │                        │                        │
          Projects                Processes                Repositories
```

---

# 8. Operating System Requirements

## OS-001 — Base Distribution

DevOS shall use Arch Linux as its base distribution.

## OS-002 — Package Management

DevOS shall use pacman as its primary system package manager.

## OS-003 — Init System

DevOS shall use systemd.

## OS-004 — Architecture

MVP shall target x86_64 systems.

## OS-005 — Boot

The ISO shall support UEFI boot.

## OS-006 — Networking

The base installation shall provide functional network connectivity.

## OS-007 — Firmware

Common hardware firmware shall be included.

## OS-008 — ISO

The project shall generate a standalone DevOS ISO.

## OS-009 — Build System

ISO generation shall use Archiso.

## OS-010 — Source Control

All DevOS-specific build configuration shall be stored in Git.

---

# 9. Desktop Requirements

## DESK-001 — Display Server

Wayland shall be the default display protocol.

## DESK-002 — Compositor

Hyprland shall be the default compositor.

## DESK-003 — Desktop Shell

The initial desktop experience shall be based on the end-4 environment.

## DESK-004 — Configuration Ownership

DevOS shall maintain its own configuration layer around the desktop environment.

DevOS must not become permanently dependent on undocumented modifications to external dotfiles.

## DESK-005 — Terminal

A modern terminal emulator shall be included.

## DESK-006 — Launcher

A graphical launcher shall be available.

The launcher should provide access to:

* applications
* commands
* development tools
* DevOS functionality
* AI assistant

## DESK-007 — Notifications

A notification system shall be available.

## DESK-008 — Status Bar

A desktop status bar shall provide essential system information.

## DESK-009 — Keyboard Driven Workflow

The desktop shall prioritize keyboard-driven workflows.

---

# 10. Developer Environment

## DEV-001 — Version Control

Git shall be installed by default.

## DEV-002 — Remote Development

OpenSSH client functionality shall be available.

## DEV-003 — C/C++

The system shall provide a C/C++ development toolchain.

Minimum components:

* GCC
* Clang
* Make
* CMake
* GDB

## DEV-004 — Python

Python development shall be supported.

## DEV-005 — JavaScript

Node.js and npm shall be supported.

## DEV-006 — TypeScript

TypeScript development shall be supported through the Node.js ecosystem.

## DEV-007 — Go

Go development shall be supported.

## DEV-008 — Rust

Rust and Cargo shall be supported.

## DEV-009 — Editor

A terminal-based developer editor shall be included.

Initial candidate:

* Neovim

## DEV-010 — CLI Tools

The following classes of tools should be available:

* ripgrep
* fd
* fzf
* jq
* tmux
* tree
* curl
* wget

## DEV-011 — Containers

The system shall support container-based development.

Docker or Podman shall be selected during technical design.

## DEV-012 — Debugging

Common debugging and system inspection tools shall be available.

---

# 11. Developer Profiles

DevOS should support predefined developer profiles.

Initial profiles:

```text
General
Web
Backend
Systems
AI
Embedded
```

A profile shall primarily represent a package and configuration preset.

Profiles shall not create separate operating-system variants.

---

# 12. AI Platform

## AI-001 — AI Interface

DevOS shall provide a graphical interface for interacting with the AI system.

## AI-002 — AI Provider

Google Gemini API shall be the primary AI provider for MVP.

## AI-003 — User API Key

The user shall provide their own Gemini API key.

DevOS shall not require a shared project-wide API key.

## AI-004 — Credential Storage

The API key shall not be stored in:

* source code
* Git repositories
* plaintext project configuration
* shell history
* application logs

The preferred storage mechanism is the desktop system keyring / Secret Service.

## AI-005 — Connection Test

The user shall be able to test the Gemini connection after entering the API key.

## AI-006 — Model Abstraction

The AI subsystem shall use a provider abstraction.

Conceptually:

```text
AI Provider
├── Gemini
├── Future Provider
├── Future Provider
└── Local Model
```

Gemini is the only required provider for MVP.

## AI-007 — Streaming

AI responses should be displayed incrementally where supported.

## AI-008 — Conversation

The AI interface shall support conversation sessions.

## AI-009 — Agent Mode

The user shall be able to transition from standard chat to agent-assisted interaction.

---

# 13. Agent System

## AGENT-001 — Agent Runtime Abstraction

DevOS shall define an abstraction between the AI platform and the Agent Runtime.

```text
AI Provider
     │
     ▼
Agent Interface
     │
     ├── Hermes
     └── Future Agent Runtime
```

## AGENT-002 — Hermes

Hermes Agent shall be evaluated as the initial Agent Runtime implementation.

Integration shall not make DevOS permanently dependent on Hermes.

## AGENT-003 — Agent Capabilities

The agent should be able to:

* inspect files
* read source code
* search projects
* inspect Git state
* inspect processes
* execute development commands
* analyze errors
* propose code changes
* modify files after approval
* run tests
* inspect system information

## AGENT-004 — Agent Activity

The user shall be able to see the agent's current operation.

Example:

```text
Agent Activity

✓ Inspecting project
✓ Reading package.json
✓ Checking Git status
→ Running tests
○ Waiting for approval
```

## AGENT-005 — Tool Calling

Agent tool calls shall be represented as structured operations.

The AI model shall request an operation.

DevOS shall decide whether and how the operation is executed.

---

# 14. System Tool Layer

The tool system shall provide controlled interfaces to operating-system functionality.

## TOOL-001 — Filesystem

Initial filesystem tools:

```text
read_file
write_file
list_directory
search_files
create_directory
```

## TOOL-002 — Terminal

Initial terminal capability:

```text
execute_command
```

Terminal execution must pass through the permission system.

## TOOL-003 — Git

Initial Git tools:

```text
git_status
git_diff
git_log
git_add
git_commit
git_branch
```

## TOOL-004 — System

Initial system tools:

```text
system_info
process_list
disk_usage
memory_usage
```

## TOOL-005 — Package Management

Initial package tools:

```text
search_package
install_package
remove_package
update_package
```

Package modification must require user approval.

---

# 15. Permission System

The permission system is a core security component of DevOS.

## 15.1 Principle

```text
AI ≠ Root
```

The agent shall not receive unrestricted root access.

## 15.2 Permission Levels

### SAFE

Operations that normally do not require confirmation.

Examples:

```text
pwd
ls
git status
git diff
read project files
system information
```

### CONFIRM

Operations requiring user approval.

Examples:

```text
write_file
git commit
package installation
package removal
process termination
service modification
configuration changes
```

### BLOCKED

Operations that are blocked by default.

Examples:

```text
filesystem formatting
destructive disk operations
credential extraction
security bypass
unrestricted privileged shell
```

---

# 16. Permission Flow

```text
User Request
     │
     ▼
AI Model
     │
     ▼
Agent
     │
     ▼
Tool Request
     │
     ▼
Permission Manager
     │
 ┌───┼─────────────┐
 │   │             │
 ▼   ▼             ▼
SAFE CONFIRM     BLOCKED
 │   │
 │   ▼
 │ User Approval
 │   │
 └───┴───────┐
             ▼
        Tool Executor
             │
             ▼
           Linux
```

---

# 17. Security Requirements

## SEC-001

The AI agent shall not have unrestricted root privileges.

## SEC-002

Sensitive operations shall require explicit user approval.

## SEC-003

API credentials shall be stored securely.

## SEC-004

Sensitive credentials shall not appear in logs.

## SEC-005

Agent operations shall be visible to the user.

## SEC-006

Tool execution shall be separated from model inference.

## SEC-007

The AI model shall never be treated as a trusted operating-system component.

## SEC-008

The permission manager shall be independent from the AI provider.

---

# 18. AI and Privacy

DevOS shall clearly distinguish between:

```text
Local Data
    │
    ├── Files
    ├── Projects
    ├── Git repositories
    └── System information

External AI
    │
    └── Gemini API
```

The system shall not transmit project or system data to Gemini unless required by an explicit user action or an agent operation authorized by the user.

The AI interface should clearly communicate when data is being sent to an external provider.

---

# 19. Logging and Observability

DevOS shall provide agent activity visibility.

Example:

```text
[14:22:01] Agent started
[14:22:03] Tool: filesystem.list
[14:22:03] Result: success
[14:22:07] Tool: terminal.execute
[14:22:07] Permission: approved
[14:22:12] Result: exit code 0
```

Sensitive information shall be excluded from logs.

---

# 20. First Boot Experience

The first boot experience should provide basic DevOS configuration.

Example:

```text
Welcome to DevOS

Configure your development environment.

Developer Profile:
[ General ]
[ Web ]
[ Backend ]
[ Systems ]
[ AI ]
[ Embedded ]

AI Configuration:
[ Configure Gemini ]
[ Skip ]
```

The AI configuration must remain optional.

DevOS must remain a functional developer operating system without an AI API key.

---

# 21. AI User Experience

The primary AI interface should provide:

```text
┌───────────────────────────────────────────────┐
│ DevOS AI                              Gemini  │
├───────────────────────────────────────────────┤
│                                               │
│ User                                          │
│ Analyze this project and find the problem.   │
│                                               │
│ Agent                                         │
│ I'll inspect the project structure.           │
│                                               │
│ ✓ list_directory                              │
│ ✓ read_file                                   │
│ ✓ git_status                                  │
│ → npm test                                    │
│                                               │
│ Waiting for approval...                       │
│                                               │
│ [ Approve ]                 [ Deny ]          │
├───────────────────────────────────────────────┤
│ Ask DevOS AI...                         [Send] │
└───────────────────────────────────────────────┘
```

---

# 22. Agent Demonstration Scenario

The primary MVP demonstration shall be:

### Step 1

Boot DevOS.

### Step 2

Enter the Hyprland desktop.

### Step 3

Open DevOS AI.

### Step 4

Configure Gemini API key.

### Step 5

Open an existing software project.

### Step 6

Ask:

```text
Analyze this project and identify the main problem.
```

### Step 7

Agent inspects:

```text
project structure
configuration
dependencies
source files
Git state
```

### Step 8

Agent proposes running a command.

Example:

```text
npm test
```

### Step 9

DevOS asks for approval.

### Step 10

User approves.

### Step 11

Agent executes the command.

### Step 12

Agent analyzes the result.

### Step 13

User requests a fix.

### Step 14

Agent proposes file modifications.

### Step 15

User approves.

### Step 16

Agent modifies the project.

### Step 17

Agent runs tests.

### Step 18

DevOS displays the final result.

This workflow represents the primary proof-of-concept for the DevOS AI-native architecture.

---

# 23. Repository Structure

The project repository should follow a modular structure.

```text
devos/
│
├── README.md
├── LICENSE
├── SRS.md
├── ROADMAP.md
├── CONTRIBUTING.md
│
├── iso/
│   ├── profile/
│   ├── packages/
│   └── build/
│
├── core/
│   ├── system/
│   ├── packages/
│   └── configuration/
│
├── desktop/
│   ├── hyprland/
│   ├── end4/
│   └── themes/
│
├── developer/
│   ├── profiles/
│   ├── runtimes/
│   └── tools/
│
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
│
├── scripts/
│
└── docs/
```

---

# 24. Build System

DevOS shall provide an automated ISO build process.

Target workflow:

```text
Clone Repository
       │
       ▼
Install Build Dependencies
       │
       ▼
Build DevOS
       │
       ▼
DevOS ISO
```

Target command:

```bash
./scripts/build-iso.sh
```

Expected output:

```text
dist/
└── devos-0.1.0-x86_64.iso
```

---

# 25. Development Workflow

The project shall follow a source-controlled development process.

```text
Requirement
    ↓
Issue
    ↓
Implementation
    ↓
Testing
    ↓
Pull Request
    ↓
Review
    ↓
Merge
```

The SRS shall remain the baseline specification.

Major architectural changes must update the SRS before implementation.

---

# 26. Versioning

DevOS shall follow Semantic Versioning.

Format:

```text
MAJOR.MINOR.PATCH
```

MVP:

```text
0.1.0
```

Future examples:

```text
0.2.0
0.3.0
1.0.0
```

---

# 27. Non-Functional Requirements

## NFR-001 — Performance

DevOS shall avoid unnecessary background services.

## NFR-002 — Startup

The desktop shall provide a responsive startup experience.

## NFR-003 — Resource Usage

The AI subsystem shall not continuously consume significant CPU, memory, or network resources when inactive.

## NFR-004 — Modularity

AI providers and agent runtimes shall be replaceable.

## NFR-005 — Maintainability

DevOS configuration shall be version-controlled.

## NFR-006 — Reproducibility

The ISO shall be reproducible from repository configuration to a reasonable extent.

## NFR-007 — Reliability

Failure of the AI subsystem shall not prevent the operating system or developer environment from functioning.

## NFR-008 — Offline Operation

Core development tools shall remain usable without an Internet connection.

---

# 28. MVP Acceptance Criteria

DevOS 0.1.0 shall be considered successful when all critical requirements below are satisfied.

## Operating System

* [ ] ISO builds successfully.
* [ ] ISO boots on UEFI systems.
* [ ] ISO boots inside a virtual machine.
* [ ] System installation succeeds.
* [ ] Installed system boots successfully.
* [ ] Network connectivity works.

## Desktop

* [ ] Hyprland starts successfully.
* [ ] end-4 environment works.
* [ ] Launcher works.
* [ ] Terminal works.
* [ ] Notifications work.
* [ ] Basic keyboard workflow works.

## Developer Environment

* [ ] Git works.
* [ ] C/C++ toolchain works.
* [ ] Python works.
* [ ] Node.js works.
* [ ] TypeScript environment works.
* [ ] Go works.
* [ ] Rust works.
* [ ] Editor works.
* [ ] Container runtime works.

## AI

* [ ] AI interface opens.
* [ ] Gemini API key can be configured.
* [ ] Gemini connection can be tested.
* [ ] Chat works.
* [ ] Streaming works where supported.
* [ ] Conversations work.
* [ ] Agent mode works.
* [ ] Filesystem tools work.
* [ ] Terminal tool works.
* [ ] Git tools work.
* [ ] Permission system works.
* [ ] Sensitive operations require confirmation.
* [ ] Agent activity is visible.

---

# 29. MVP Definition of Done

Phase 1 is complete when a user can:

```text
Install DevOS
      ↓
Boot DevOS
      ↓
Enter Hyprland
      ↓
Use developer tools
      ↓
Open a project
      ↓
Open DevOS AI
      ↓
Connect Gemini
      ↓
Start Agent
      ↓
Inspect project
      ↓
Execute approved tools
      ↓
Modify project
      ↓
Run tests
      ↓
Complete development task
```

without requiring manual installation of the core developer environment.

---

# 30. Phase 1 Roadmap

## Phase 1.0 — Foundation

* Archiso integration
* DevOS repository
* Build system
* Base system
* Core packages
* ISO generation

## Phase 1.1 — Desktop

* Hyprland
* end-4
* terminal
* launcher
* notifications
* themes
* desktop configuration

## Phase 1.2 — Developer Environment

* programming languages
* Git
* editors
* debugging tools
* containers
* developer profiles

## Phase 1.3 — AI Client

* AI UI
* Gemini provider
* API key management
* streaming
* conversation system

## Phase 1.4 — Agent

* Agent Runtime abstraction
* Hermes integration
* filesystem tools
* terminal tools
* Git tools
* system tools

## Phase 1.5 — Security

* permission manager
* approval workflow
* privileged operation handling
* logging
* credential protection

## Phase 1.6 — Integration

* Desktop ↔ AI
* AI ↔ Agent
* Agent ↔ Tools
* Tools ↔ Linux
* complete developer workflow

## Phase 1.7 — MVP Release

* VM testing
* hardware testing
* documentation
* installation testing
* security review
* DevOS 0.1.0 release

---

# 31. Future Roadmap

The following capabilities may be considered after MVP:

```text
Local LLM
Multi-model support
Multi-agent architecture
Voice interface
Computer vision
Background agents
Scheduled agents
Agent marketplace
Skill marketplace
AI memory
Cloud synchronization
Mobile companion
AI-assisted package management
AI system administration
Self-diagnosis
Self-healing workflows
AI-assisted OS configuration
```

---

# 32. Core Architectural Principle

The central architectural principle of DevOS is:

```text
AI should operate the system through DevOS,
not around DevOS.
```

The intended architecture is:

```text
              ┌─────────────┐
              │    User     │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ DevOS AI UI │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │    Agent    │
              └──────┬──────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Permission Layer│
            └────────┬────────┘
                     │
                     ▼
             ┌───────────────┐
             │ Tool Executor │
             └───────┬───────┘
                     │
                     ▼
                 Linux OS
```

This architecture allows DevOS to evolve from an AI-assisted developer environment into a genuinely AI-native operating system without requiring the AI model itself to become part of the trusted operating-system core.

---

# 33. Success Metric

The primary success criterion for DevOS MVP is not the number of preinstalled packages or the visual appearance of the desktop.

The primary success criterion is:

> A developer can install DevOS, enter a ready-to-use development environment, connect their own Gemini account, interact with an AI agent, allow that agent to inspect and operate on development projects, and maintain explicit control over system-changing operations.

---

# 34. Document Status

**Document Owner:** Ehsan Fazli
**Project:** DevOS
**Version:** 0.1.0
**Status:** Draft
**Target Repository:** GitHub / DevOS

```text
SRS v0.1.0
      │
      ▼
Architecture Baseline
      │
      ▼
Implementation
      │
      ▼
Testing
      │
      ▼
DevOS 0.1.0
```

Any major change to the project scope, architecture, security model, AI provider architecture, agent architecture, or desktop architecture shall require an update to this document.
