#!/usr/bin/env bash
# Verify package lists against the official Arch repositories (SRS OS-012, BLD-004).
#
# Every entry must exist in core/extra (or be a group there), or in the [devos]
# repo (a configured one, or a local build passed with -r). Duplicates are
# reported. Exit status 1 on any problem.
#
# Usage: scripts/check-packages.sh [-r REPO_DIR] [list ...]   (default: iso/packages.x86_64)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_REPO=""
if [[ "${1:-}" == "-r" ]]; then
    LOCAL_REPO="$2"
    shift 2
fi
(( $# )) || set -- "$ROOT/iso/packages.x86_64"

REPOS=(core extra)
pacman -Sl devos &>/dev/null && REPOS+=(devos)

declare -A known=()
while read -r _ name _; do known[$name]=1; done < <(pacman -Sl "${REPOS[@]}")
while read -r group _; do known[$group]=1; done < <(pacman -Sg | sort -u)
if [[ -n "$LOCAL_REPO" ]]; then
    [[ -f "$LOCAL_REPO/devos.db.tar.zst" ]] || { echo "no devos.db.tar.zst in $LOCAL_REPO" >&2; exit 1; }
    REPOS+=("devos (local)")
    # Database entries are "<name>-<pkgver>-<pkgrel>/"
    while read -r entry; do
        entry="${entry%/}"
        known[${entry%-*-*}]=1
    done < <(bsdtar -tf "$LOCAL_REPO/devos.db.tar.zst" | grep -E '^[^/]+/$')
fi
(( ${#known[@]} )) || { echo "pacman -Sl returned nothing; run 'pacman -Sy' first" >&2; exit 1; }

status=0
for list in "$@"; do
    declare -A seen=()
    while IFS= read -r line; do
        pkg="${line%%#*}"
        pkg="${pkg//[[:space:]]/}"
        [[ -z "$pkg" ]] && continue
        if [[ -n "${seen[$pkg]:-}" ]]; then
            echo "$list: duplicate: $pkg"
            status=1
        fi
        seen[$pkg]=1
        if [[ -z "${known[$pkg]:-}" ]]; then
            echo "$list: not in ${REPOS[*]}: $pkg"
            status=1
        fi
    done <"$list"
    echo "$list: ${#seen[@]} packages checked"
    unset seen
done
exit "$status"
