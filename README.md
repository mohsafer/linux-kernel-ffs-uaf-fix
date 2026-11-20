# linux-ffs-uaf-fix

Fix for the syzbot bug **"KASAN: slab-use-after-free Write in
`ffs_data_clear`"** ([extid 6227549bd2c8a1ec8ba0](https://syzkaller.appspot.com/bug?extid=6227549bd2c8a1ec8ba0))
in the Linux kernel USB gadget FunctionFS driver
(`drivers/usb/gadget/function/f_fs.c`).

## The bug

`ffs_free_inst()` (the configfs `rmdir` path) released the `struct ffs_dev`
and only then re-acquired `ffs_dev_lock` to free it. In that window the dev
was still on the global `ffs_devices` list while already marked unmounted,
so a concurrent `mount(2)` of functionfs found it by name and linked a fresh
`ffs_data` to the doomed dev. The dev was then `kfree()`d out from under
that mount, and when the mount was torn down (`umount` → `kill_sb` →
`ffs_data_clear` → `ffs_closed`), the driver wrote
`ffs_obj->desc_ready = false` into freed memory. The defective shape — the
release-then-free window and the unlocked `private_data` read — dates back
to commit `ecfbd7b9054b` (2021); the configfs interface itself came with
`5920cda627688c` (2013). A related read-side TOCTOU in `ffs_data_put()`
(unlocked argument read of `ffs->private_data`) is also fixed.

## The fix

- Hold `ffs_dev_lock` across the release and the free in `ffs_free_inst()`,
  so a released dev is never findable.
- Re-read `ffs->private_data` under `ffs_dev_lock` in `ffs_data_put()`.
- Enforce the caller-holds-the-lock contract of `_ffs_release_dev()`
  with `lockdep_assert_held(&ffs_lock)` (v3, per Greg KH's review).

The complete patch is [`0001-usb-gadget-f_fs-fix-use-after-free-in-ffs_closed-on-.patch`](0001-usb-gadget-f_fs-fix-use-after-free-in-ffs_closed-on-.patch)
(`[PATCH v4]`, mbox format — applies with `git am`; bare diff in
[`fix.diff`](fix.diff)). Posted to the linux-usb mailing list:
[thread](https://lore.kernel.org/linux-usb/?q=%22fix+use-after-free+in+ffs_closed%22).

## Verification

- Reproducer (`repro/`) reproduces syzbot's exact crash signature on an
  unpatched v7.3-rc6 KASAN kernel (2/2 runs).
- Patched kernel: clean in all runs, including a 300 s soak with 6,290
  mounts / 24,532 mkdir-rmdir cycles (~16× the churn that triggers the
  unpatched kernel). Archived console logs in `repro/*_run*.log`.
- `scripts/checkpatch.pl`: 0 errors (the lone `Fixes:` commit-id warning
  is a no-tree artifact); `git am` on a pristine tree: applies cleanly,
  resulting-file blob hash verified (v4).
- v4 + `CONFIG_PROVE_LOCKING=y` (KASAN + lockdep kernel): clean — 60 s
  and 180 s soaks with the same harness. The churn runs every caller of
  the `lockdep_assert_held()`-guarded `_ffs_release_dev()` (13,296
  mkdir-rmdir / 2,304 mount-umount cycles in the 180 s run) with zero
  lockdep splats (`repro/lockdep_soak180.log`).

## Reproducing

```bash
bash repro/config_build.sh        # defconfig + KASAN + USB gadget/configfs kernel
bash repro/build_initramfs.sh     # static reproducer + busybox initramfs
bash repro/run_qemu.sh <bzImage> 60
# RESULT: UAF REPRODUCED on unpatched trees, RESULT: clean with the fix applied
```

## Files

- `0001-usb-gadget-f_fs-*.patch` — the `[PATCH v4]` email (mbox, `git am`-ready)
- `fix.diff` — bare diff of the fix
- `repro/` — reproducer source, QEMU/initramfs harness, kernel build script, run logs
- `f_fs_master.c`, `f_fs_next.c`, `u_fs.h`, `f_fs.h` — analyzed kernel sources
- `ffshist.atom`, `mm_lifetime.patch` — commit-history evidence (cgit)
- `upstream.html` — syzbot upstream dashboard snapshot (2026-10-06)

## References

- syzbot report: <https://syzkaller.appspot.com/bug?extid=6227549bd2c8a1ec8ba0>
- Submitting patches: <https://docs.kernel.org/process/submitting-patches.html>
- KASAN: <https://docs.kernel.org/dev-tools/kasan.html>
