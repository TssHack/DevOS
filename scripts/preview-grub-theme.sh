#!/usr/bin/env bash
# Boot the DevOS live GRUB menu + theme in QEMU/OVMF and save a screenshot,
# without building the ISO. GRUB is built like mkarchiso builds it
# (grub-mkstandalone, same module list), so what you see is what the ISO shows.
#
# Requires: grub, qemu-system-x86_64, edk2-ovmf, mtools, python
# Usage:    scripts/preview-grub-theme.sh [-m 1920x1080] [-o out.png] [-d seconds] [-t seconds] [-k keys] [-i]
#   -m  force a GRUB gfxmode (default: the cfg's own list)
#   -o  screenshot path (default: dist/grub-preview.png)
#   -d  seconds to wait before the screenshot (default: 16)
#   -t  GRUB menu timeout (default: 60, so the countdown is still visible)
#   -k  QEMU key names to send before the screenshot, comma separated (e.g. "down,down")
#   -i  interactive: open a QEMU window instead of taking a screenshot

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE=""
OUT="$ROOT/dist/grub-preview.png"
DELAY=16
GRUB_TIMEOUT=60
KEYS=""
INTERACTIVE=false
while getopts "m:o:d:t:k:i" opt; do
    case "$opt" in
        m) MODE="$OPTARG" ;;
        o) OUT="$OPTARG" ;;
        d) DELAY="$OPTARG" ;;
        t) GRUB_TIMEOUT="$OPTARG" ;;
        k) KEYS="$OPTARG" ;;
        i) INTERACTIVE=true ;;
        *) sed -n '2,14p' "$0"; exit 1 ;;
    esac
done

OVMF_CODE=/usr/share/edk2/x64/OVMF_CODE.4m.fd
OVMF_VARS=/usr/share/edk2/x64/OVMF_VARS.4m.fd
for f in "$OVMF_CODE" "$OVMF_VARS"; do [[ -f "$f" ]] || { echo "missing $f (install edk2-ovmf)" >&2; exit 1; }; done

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
VERSION="$(cat "$ROOT/VERSION")"

# Same module list as mkarchiso's _make_bootmode_uefi.grub
MODULES="all_video at_keyboard boot btrfs cat chain configfile echo efifwsetup efinet exfat ext2 f2fs fat font
gfxmenu gfxterm gzio halt hfsplus iso9660 jpeg keylayouts linux loadenv loopback lsefi lsefimmap
minicmd normal ntfs ntfscomp part_apple part_gpt part_msdos png read reboot regexp search
search_fs_file search_fs_uuid search_label serial sleep tpm udf usb usbserial_common usbserial_ftdi
usbserial_pl2303 usbserial_usbdebug video xfs zstd"

cat >"$WORK/embed.cfg" <<'EOF'
search --no-floppy --set=root --file /devos-preview
configfile /boot/grub/grub.cfg
EOF
grub-mkstandalone -O x86_64-efi --modules="$(echo $MODULES)" --locales="en@quot" --themes="" \
    --disable-shim-lock -o "$WORK/BOOTX64.EFI" "boot/grub/grub.cfg=$WORK/embed.cfg"

mkdir -p "$WORK/fs/EFI/BOOT" "$WORK/fs/boot/grub/themes"
cp "$WORK/BOOTX64.EFI" "$WORK/fs/EFI/BOOT/"
cp -r "$ROOT/boot/grub/themes/devos" "$WORK/fs/boot/grub/themes/"
touch "$WORK/fs/devos-preview"
sed -e "s|%DEVOS_VERSION%|$VERSION|g; s|%INSTALL_DIR%|devos|g; s|%ARCH%|x86_64|g;
        s|%ARCHISO_UUID%|preview|g; s|%KERNEL_PARAMS%||g" \
    "$ROOT/iso/grub/grub.cfg" >"$WORK/fs/boot/grub/grub.cfg"
sed -i "s|^timeout=.*|timeout=$GRUB_TIMEOUT|" "$WORK/fs/boot/grub/grub.cfg"
[[ -n "$MODE" ]] && sed -i "s|^set gfxmode=.*|set gfxmode=$MODE|" "$WORK/fs/boot/grub/grub.cfg"

truncate -s 64M "$WORK/esp.img"
mformat -i "$WORK/esp.img" -F ::
mcopy -s -i "$WORK/esp.img" "$WORK/fs/"* ::

cp "$OVMF_VARS" "$WORK/vars.fd"
QEMU=(qemu-system-x86_64 -machine q35 -m 512 -accel kvm -accel tcg
      -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE"
      -drive if=pflash,format=raw,file="$WORK/vars.fd"
      -drive format=raw,file="$WORK/esp.img"
      -vga std -net none)

if $INTERACTIVE; then
    exec "${QEMU[@]}"
fi

mkdir -p "$(dirname "$OUT")"
"${QEMU[@]}" -display none -qmp "unix:$WORK/qmp.sock,server=on,wait=off" &
QPID=$!
python3 - "$WORK/qmp.sock" "$DELAY" "$KEYS" "$OUT" <<'EOF'
import json, socket, sys, time
sock_path, delay, keys, out = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
for _ in range(50):
    try:
        s = socket.socket(socket.AF_UNIX); s.connect(sock_path); break
    except OSError:
        time.sleep(0.1)
f = s.makefile("rw")
def cmd(name, **args):
    f.write(json.dumps({"execute": name, "arguments": args}) + "\n"); f.flush()
    while True:
        r = json.loads(f.readline())
        if "return" in r or "error" in r:
            return r
f.readline(); cmd("qmp_capabilities")
time.sleep(delay)
for k in filter(None, keys.split(",")):
    cmd("send-key", keys=[{"type": "qcode", "data": k}]); time.sleep(0.4)
time.sleep(0.5)
r = cmd("screendump", filename=out, format="png")
if "error" in r:
    sys.exit(f"screendump failed: {r['error']}")
cmd("quit")
EOF
wait "$QPID" 2>/dev/null || true
echo "screenshot: $OUT"
