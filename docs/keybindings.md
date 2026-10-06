# Keybindings

SRS DESK-009. DevOS uses end-4's keybindings (see `~/.config/hypr/hyprland/keybinds.lua`,
or press Super+/ for the cheatsheet) with one change. Verified against end-4 commit 2f0c8bf.

| Keys | Action |
|---|---|
| **Super+A** | **DevOS AI panel** (DevOS; end-4's left sidebar moves to Super+B / Super+O) |
| Super+Enter (or Super+T) | Terminal (kitty) |
| Super (tap) | Search / launcher |
| Super+C | Code editor |
| Super+Q | Close window |
| Super+1 … Super+0 | Switch workspace 1–10 |
| Super+L | Lock screen |
| Print / Super+Shift+S | Screenshot |

In the DevOS AI panel: Enter sends, Shift+Enter adds a line, Tab moves between
buttons, Enter/Space activates the focused button, **Esc denies a pending
approval** (otherwise closes the panel). Approve is never bound to a global key (UX-001).
