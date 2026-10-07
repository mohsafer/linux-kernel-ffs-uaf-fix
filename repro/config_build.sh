#!/bin/bash
# Configure and build a KASAN kernel for the ffs repro (defconfig base).
set -e
cd ~/kernelbug/linux
make defconfig
./scripts/config \
	-e KASAN -e KASAN_GENERIC -e KASAN_INLINE -d KASAN_OUTLINE \
	-e CONFIGFS_FS \
	-e USB_GADGET -e USB_CONFIGFS -e USB_CONFIGFS_F_FS \
	-d DEBUG_INFO_BTF -d DEBUG_INFO_BTF_MODULES
make olddefconfig
echo "=== key config lines ==="
grep -E "^CONFIG_(KASAN|CONFIGFS_FS|USB_GADGET|USB_CONFIGFS|USB_F_FS|FUNCTIONFS)" .config | sort
echo "=== building (40 jobs) ==="
time make -j40 bzImage
echo BUILD_DONE
ls -la arch/x86/boot/bzImage
