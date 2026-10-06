# DevOS Roadmap

Derived from [SRS §27](SRS.md). A phase is done when its acceptance tests (SRS §26) pass.

## Phase 1.0 — Foundation
- [x] Archiso profile moved to `iso/`, GRUB (UEFI) as the only bootloader
- [x] `profiledef.sh` fixed; version from `VERSION`; zstd squashfs
- [x] Minimal, valid live package list + `scripts/check-packages.sh` (A-02)
- [x] Live system networking on NetworkManager; unused upstream services removed
- [x] DevOS GRUB theme + render and QEMU preview scripts (A-05b, verified in QEMU)
- [x] `devos-grub-theme` PKGBUILD
- [ ] First ISO build and UEFI boot in REF-VM (A-01, A-03)
- [x] CI workflow: shellcheck, package check, AI tests, repo + ISO build (BLD-007)
- [ ] QEMU boot smoke test in CI

## Phase 1.1 — Desktop
- [x] `[devos]` package repo + `scripts/build-repo.sh` (pending packages skipped)
- [x] `devos-desktop` PKGBUILD (end-4 pinned at 2f0c8bf), Super+A patch, Lua overrides
- [x] `devos-quickshell` PKGBUILD (end-4's pinned Quickshell commit)
- [x] greetd + tuigreet config, keyring unlock via PAM
- [ ] `devos-fonts`: pin upstream commits + checksums (needs network)
- [ ] Build devos-desktop / devos-quickshell (needs network), then A-07, A-08 in a VM

## Phase 1.2 — Developer Environment
- [x] Six profiles as package lists + `devos-profile-*` metapackages, validated
- [ ] Rootless Podman check and toolchain smoke tests in a VM (A-09, A-10)

## Phase 1.3 — Installer and First Boot
- [x] `devos-install` (direct, TUI + `--config` + `--post`), `devos-installer` package
- [x] Welcome window (DevOS shell)
- [ ] Run the installer in REF-VM, UEFI boot of the installed system (A-04, A-05, A-11)

## Phase 1.4a — AI Core
- [x] devosd, IPC, Secret Service, Gemini REST provider, streaming chat, conversations
- [x] AI panel (Quickshell), status pill, CLI
- [ ] Test against the real Gemini API with a key (A-13, A-14)

## Phase 1.4b — Hermes Spike
- [x] ADR 0001: native runtime for 0.1.0
- [ ] Hermes evaluation against SRS §14.4 (needs network + key)

## Phase 1.5 — Agent and Security
- [x] Tool registry, Permission Manager, 298-case corpus, bubblewrap sandbox, pkg-helper, audit, undo, native runtime — 58 tests (A-15–A-19 automated)
- [ ] Real pkexec/polkit flow on an installed system (A-20)
- [ ] Package signing (SEC-011), Podman sandbox exception

## Phase 1.6 — Integration
- [x] Status indicator, approval notifications, settings (CLI + IPC)
- [ ] Settings page in the panel, `examples/demo-node`, measurements (A-21, A-22)

## Phase 1.7 — Release
- [ ] Hardware tests, documentation, security review, DevOS 0.1.0 (all of SRS §26)
