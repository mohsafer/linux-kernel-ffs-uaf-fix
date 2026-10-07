#!/bin/bash
# Boot a kernel in QEMU with the repro initramfs and check for KASAN reports.
# usage: run_qemu.sh <bzImage> [repro_seconds]
set -u
K=${1:?usage: run_qemu.sh <bzImage> [repro_seconds]}
S=${2:-45}
cd ~/kernelbug/repro
timeout $((S + 90)) qemu-system-x86_64 \
	-m 4G -smp 8 \
	-kernel "$K" \
	-initrd initramfs.cpio.gz \
	-append "console=ttyS0 panic=-1 kasan.multi_shot=1 REPRO_SECS=$S" \
	-nographic -no-reboot -monitor none \
	> last_boot.log 2>&1
rc=$?
echo "qemu rc=$rc, log size $(wc -l < last_boot.log) lines"
if grep -q "slab-use-after-free" last_boot.log; then
	echo "RESULT: UAF REPRODUCED"
	grep -n -m1 -A 40 "BUG: KASAN" last_boot.log
elif grep -qE "BUG: kernel NULL|Oops|kernel BUG|BUG: unable" last_boot.log; then
	echo "RESULT: OTHER KERNEL BUG"
	grep -nE "BUG|Oops" last_boot.log | head -10
else
	echo "RESULT: clean (no KASAN report)"
fi
