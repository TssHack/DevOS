# Enabled services (SRS NFR-001)

## Installed system

| Unit | Scope | Why |
|---|---|---|
| `NetworkManager.service` | system | networking (OS-006) |
| `systemd-timesyncd.service` | system | clock sync |
| `fstrim.timer` | system | SSD trim |
| `greetd.service` | system | login (DESK-010) |
| `devosd.socket` | user | DevOS AI, socket-activated: no process until first use; devosd exits after 10 idle minutes when nothing is connected |

Hyprland/end-4 start their own user processes (Quickshell shell, hypridle, portals).
Nothing else is enabled by DevOS.

## Live ISO

`NetworkManager`, `systemd-resolved`, `systemd-timesyncd`, `sshd` (root has no
password, so SSH login is impossible until one is set), `pacman-init`, `choose-mirror`.
