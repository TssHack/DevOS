#!/usr/bin/env bash
# Render the DevOS GRUB theme from SVG/font sources.
#
# Sources:  boot/grub/src/        (SVG artwork, icons)
#           boot/grub/theme.txt   (layout)
# Output:   boot/grub/themes/devos/   (committed, so ISO builds need no render tools)
#
# Requires: librsvg (rsvg-convert), imagemagick (magick), grub (grub-mkfont),
#           ttf-jetbrains-mono, otf-space-grotesk (only for the logo wordmark).
# Usage:    scripts/render-grub-theme.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/boot/grub/src"
OUT="$ROOT/boot/grub/themes/devos"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

for cmd in rsvg-convert magick grub-mkfont; do
    command -v "$cmd" >/dev/null || { echo "missing: $cmd" >&2; exit 1; }
done

# Prefer the official package's files; fall back to the Nerd Font build (same glyphs).
find_font() {
    local f
    for f in "$@"; do
        [[ -f "$f" ]] && { echo "$f"; return; }
    done
    echo "font not found: $*" >&2
    exit 1
}
MONO_REGULAR="$(find_font /usr/share/fonts/TTF/JetBrainsMono-Regular.ttf /usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf)"
MONO_BOLD="$(find_font /usr/share/fonts/TTF/JetBrainsMono-Bold.ttf /usr/share/fonts/TTF/JetBrainsMonoNerdFont-Bold.ttf)"

rm -rf "$OUT"
mkdir -p "$OUT/icons"

# --- Background -------------------------------------------------------------
# Baseline JPEG (GRUB cannot decode progressive), 4:4:4 to keep the glows clean.
# Grain in the SVG prevents banding; JPEG keeps it small and fast to decode.
rsvg-convert "$SRC/background.svg" -o "$TMP/background.png"
magick "$TMP/background.png" -strip -sampling-factor 4:4:4 -interlace none -quality 92 "$OUT/background.jpg"

# --- Logo -------------------------------------------------------------------
rsvg-convert -z 0.75 "$SRC/logo.svg" -o "$TMP/logo.png"
magick "$TMP/logo.png" -trim +repage -bordercolor none -border 8 -strip "$OUT/logo.png"

# --- Icons (32 px) ----------------------------------------------------------
for svg in "$SRC"/icons/*.svg; do
    name="$(basename "$svg" .svg)"
    {
        echo '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24"'
        echo '     fill="none" stroke="#C9D3E3" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        cat "$svg"
        echo '</svg>'
    } >"$TMP/$name.svg"
    rsvg-convert "$TMP/$name.svg" -o "$OUT/icons/$name.png"
done

# GRUB picks the first --class of an entry that has an icon. Map common classes.
alias_icon() { local src="$1"; shift; for a in "$@"; do cp "$OUT/icons/$src.png" "$OUT/icons/$a.png"; done; }
alias_icon devos     arch
alias_icon linux     gnu-linux gnu os
alias_icon firmware  efi uefi-firmware
alias_icon memtest   memtest86
alias_icon shutdown  poweroff halt
alias_icon reboot    restart
alias_icon windows   window

# --- 9-slice pixmaps --------------------------------------------------------
# slice NAME SVG W H K  ->  NAME_{nw,n,ne,w,c,e,sw,s,se}.png, corner size K.
slice() {
    local name="$1" svg="$2" w="$3" h="$4" k="$5"
    local iw=$((w - 2 * k)) ih=$((h - 2 * k))
    # A zero-sized middle would make ImageMagick crop the full dimension.
    (( iw > 0 && ih > 0 )) || { echo "slice $name: middle must be non-empty" >&2; exit 1; }
    printf '%s' "$svg" >"$TMP/$name.svg"
    rsvg-convert "$TMP/$name.svg" -o "$TMP/$name.png"
    local -A geo=(
        [nw]="${k}x${k}+0+0"        [n]="${iw}x${k}+${k}+0"        [ne]="${k}x${k}+$((w - k))+0"
        [w]="${k}x${ih}+0+${k}"     [c]="${iw}x${ih}+${k}+${k}"    [e]="${k}x${ih}+$((w - k))+${k}"
        [sw]="${k}x${k}+0+$((h - k))" [s]="${iw}x${k}+${k}+$((h - k))" [se]="${k}x${k}+$((w - k))+$((h - k))"
    )
    local part
    for part in "${!geo[@]}"; do
        magick "$TMP/$name.png" -crop "${geo[$part]}" +repage -strip "PNG32:$OUT/${name}_${part}.png"
    done
}

# Menu panel: translucent surface with a hairline border.
slice menu '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96">
  <rect x="0.5" y="0.5" width="95" height="95" rx="18" fill="#0B111B" fill-opacity="0.68"
        stroke="#FFFFFF" stroke-opacity="0.08"/></svg>' 96 96 20

# Selected item: soft teal->violet wash, teal hairline, accent bar on the left edge.
slice select '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="56">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#2DD4BF" stop-opacity="0.24"/>
      <stop offset="1" stop-color="#8B5CF6" stop-opacity="0.14"/>
    </linearGradient>
    <clipPath id="r"><rect x="0" y="0" width="120" height="56" rx="12"/></clipPath>
  </defs>
  <rect x="0.5" y="0.5" width="119" height="55" rx="11.5" fill="url(#g)" stroke="#2DD4BF" stroke-opacity="0.50"/>
  <rect x="0" y="0" width="4" height="56" fill="#2DD4BF" clip-path="url(#r)"/></svg>' 120 56 12

# Console / editor box.
slice terminal_box '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96">
  <rect x="0.5" y="0.5" width="95" height="95" rx="14" fill="#080C14" fill-opacity="0.92"
        stroke="#2DD4BF" stroke-opacity="0.25"/></svg>' 96 96 16

# Timeout bar: track and gradient fill. Centre piece only: GRUB draws the
# highlight offset by the track's border size, so borders would misalign them.
# GRUB also enforces a minimum bar height (from its font), and scales the
# piece to fit, so the source is a 3:20 line centred in transparent space.
center_only() {
    printf '%s' "$2" >"$TMP/$1.svg"
    rsvg-convert "$TMP/$1.svg" -o "$TMP/$1.png"
    magick "$TMP/$1.png" -strip "PNG32:$OUT/${1}_c.png"
}
center_only progress_bar '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="20">
  <rect y="8.5" width="64" height="3" fill="#FFFFFF" fill-opacity="0.10"/></svg>'
center_only progress_highlight '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="20">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#2DD4BF"/><stop offset="1" stop-color="#8B5CF6"/></linearGradient></defs>
  <rect y="8.5" width="256" height="3" fill="url(#g)"/></svg>'

# Scrollbar.
slice scrollbar_frame '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="24">
  <rect x="1" width="6" height="24" rx="3" fill="#FFFFFF" fill-opacity="0.06"/></svg>' 8 24 3
slice scrollbar_thumb '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="24">
  <rect x="1" width="6" height="24" rx="3" fill="#2DD4BF" fill-opacity="0.75"/></svg>' 8 24 3

# --- Fonts ------------------------------------------------------------------
# GRUB fonts are 1-bit bitmaps; hinted JetBrains Mono stays crisp at these sizes.
# Limit glyph ranges to keep files small and loading fast.
RANGES='0x20-0x7E,0xA0-0xFF,0x2010-0x2027,0x2190-0x2193,0x2500-0x257F,0x2580-0x259F'
mkfont() { grub-mkfont -n "DevOS Mono" -r "$RANGES" -s "$2" -o "$OUT/$3" "$1"; }
mkfont "$MONO_REGULAR" 16 devos-mono-16.pf2
mkfont "$MONO_REGULAR" 20 devos-mono-20.pf2
mkfont "$MONO_BOLD"    20 devos-mono-bold-20.pf2

# --- Theme file and licenses ------------------------------------------------
read -r LOGO_W LOGO_H < <(magick identify -format '%w %h\n' "$OUT/logo.png")
sed -e "s/@LOGO_W@/$LOGO_W/" -e "s/@LOGO_H@/$LOGO_H/" -e "s/@LOGO_HALF_W@/$((LOGO_W / 2))/" \
    "$ROOT/boot/grub/theme.txt" >"$OUT/theme.txt"
cp "$ROOT/boot/grub/LICENSE-fonts" "$OUT/LICENSE-fonts"

du -sh "$OUT"
