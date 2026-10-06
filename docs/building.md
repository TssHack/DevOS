# Building DevOS

## Requirements (Arch host)

`archiso grub mtools base-devel git` (+ `qemu-full edk2-ovmf` to test, `librsvg imagemagick ttf-jetbrains-mono` to re-render the GRUB theme).

## Steps

```bash
scripts/build-repo.sh                 # 1. build packaging/* into repo/x86_64 (as your user)
sudo scripts/build-iso.sh             # 2. build dist/devos-<VERSION>-x86_64.iso
```

`build-repo.sh -c` builds in clean chroots (devtools). Packages with a `.pending`
file are skipped until their sources are pinned (currently `devos-fonts`, which
`devos-desktop` needs).

## Checks

```bash
scripts/check-packages.sh -r repo/x86_64 iso/packages.x86_64 developer/profiles/*.list
cd ai && PYTHONPATH=.:tests python -m unittest discover -s tests
scripts/preview-grub-theme.sh -m 1920x1080       # GRUB theme in QEMU
```

## Test in a VM (REF-VM)

```bash
qemu-system-x86_64 -enable-kvm -machine q35 -m 8G -smp 4 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
  -drive if=pflash,format=raw,file=ovmf_vars.fd \
  -device virtio-vga-gl -display gtk,gl=on \
  -drive file=disk.qcow2,if=virtio -cdrom dist/devos-0.1.0-x86_64.iso
```

(`cp /usr/share/edk2/x64/OVMF_VARS.4m.fd ovmf_vars.fd` and `qemu-img create -f qcow2 disk.qcow2 64G` first.)
Hyprland needs GPU acceleration: use `virtio-vga-gl` with `gl=on` (SRS §5.3).
