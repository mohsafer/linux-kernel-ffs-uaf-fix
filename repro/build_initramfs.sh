#!/bin/bash
# Build static repro + initramfs on the server.
set -e
cd ~/kernelbug/repro
gcc -static -O2 -Wall -o repro repro.c -lpthread
echo "repro built: $(file repro | cut -d, -f2)"

rm -rf initramfs
mkdir -p initramfs/{bin,dev,proc,sys,tmp,sys/kernel/config,mnt/ffs0,mnt/ffs1,mnt/ffs2,mnt/ffs3}
cp /bin/busybox initramfs/bin/busybox
cp repro initramfs/repro
cp init initramfs/init
chmod +x initramfs/init
(cd initramfs && find . | cpio -o -H newc --owner root:root 2>/dev/null | gzip -9) > initramfs.cpio.gz
ls -la initramfs.cpio.gz
echo INITRAMFS_OK
