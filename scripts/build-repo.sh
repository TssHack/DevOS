#!/usr/bin/env bash
# Build all DevOS packages into the [devos] pacman repository (SRS BLD-003, OS-011).
#
# Usage: scripts/build-repo.sh [-o REPO_DIR] [-c] [-s] [PACKAGE_DIR ...]
#   -o  repository directory (default: repo/x86_64)
#   -c  build in a clean chroot with devtools (extra-x86_64-build); default is makepkg
#   -s  install build dependencies (sudo pacman) for packages that compile code;
#       metapackages and file-only packages never need them
#   Packages default to every directory in packaging/.
# Signing: set DEVOS_SIGN_KEY=<gpg key id> to sign packages and the database.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$ROOT/repo/x86_64"
CHROOT=false
SYNCDEPS=false
while getopts "o:csh" opt; do
    case "$opt" in
        o) REPO_DIR="$(realpath -m "$OPTARG")" ;;
        c) CHROOT=true ;;
        s) SYNCDEPS=true ;;
        *) sed -n '2,11p' "$0"; exit 1 ;;
    esac
done
shift $((OPTIND - 1))
if (( $# == 0 )); then
    # Packages marked .pending are skipped unless named explicitly.
    for d in "$ROOT"/packaging/*/; do
        if [[ -e "$d/.pending" ]]; then
            echo "skipping $(basename "$d"): $(cat "$d/.pending")" >&2
        else
            set -- "$@" "$d"
        fi
    done
fi

log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
(( EUID != 0 )) || { echo "do not run as root (makepkg refuses)" >&2; exit 1; }
mkdir -p "$REPO_DIR"
SIGN=()
[[ -n "${DEVOS_SIGN_KEY:-}" ]] && SIGN=(--sign --key "$DEVOS_SIGN_KEY")

built=()
for dir in "$@"; do
    dir="$(realpath "$dir")"
    name="$(basename "$dir")"
    log "Building $name"
    if $CHROOT; then
        (cd "$dir" && extra-x86_64-build -- -- --noconfirm)
        mv "$dir"/*.pkg.tar.zst "$REPO_DIR"/
    else
        deps=(--nodeps)
        if $SYNCDEPS && grep -q '^build()' "$dir/PKGBUILD"; then
            deps=(--syncdeps --needed)
        fi
        (cd "$dir" && PKGDEST="$REPO_DIR" BUILDDIR="$ROOT/work/makepkg" SRCDEST="${SRCDEST:-$ROOT/work/sources}" makepkg -f --noconfirm "${SIGN[@]}" \
            "${deps[@]}" 2>&1 | sed "s/^/  [$name] /")
    fi
    built+=("$name")
done

log "Updating repository database"
shopt -s nullglob
pkgs=("$REPO_DIR"/*.pkg.tar.zst)
(( ${#pkgs[@]} )) || { echo "no packages built" >&2; exit 1; }
repo-add --remove "${SIGN[@]}" "$REPO_DIR/devos.db.tar.zst" "${pkgs[@]}" >/dev/null
log "Repository: $REPO_DIR (${#pkgs[@]} packages: ${built[*]})"
