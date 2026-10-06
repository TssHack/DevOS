#!/usr/bin/env bash
# shellcheck disable=SC2034
#
# DevOS archiso profile. Sourced by mkarchiso.
# DEVOS_VERSION is exported by scripts/build-iso.sh from the VERSION file.

iso_name="devos"
iso_label="DEVOS_${DEVOS_VERSION:-dev}"
iso_label="${iso_label//./_}"
iso_publisher="DevOS <https://github.com/DevOS>"
iso_application="DevOS Live Environment"
iso_version="${DEVOS_VERSION:-0.0.0-dev}"
install_dir="devos"
# UEFI only (SRS D-01, OS-005). GRUB with the DevOS theme (SRS §6.1 BOOT-*).
bootmodes=('uefi.grub')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
# zstd: several times faster to decompress than xz, at a small size cost (SRS NFR-002).
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '19' '-b' '1M')
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/root/.automated_script.sh"]="0:0:755"
  ["/root/.gnupg"]="0:0:700"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
)
