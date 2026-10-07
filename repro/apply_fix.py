#!/usr/bin/env python3
"""Apply the ffs_free_inst race fix to drivers/usb/gadget/function/f_fs.c.
Run from the top of the kernel tree on the server."""
import sys

PATH = "drivers/usb/gadget/function/f_fs.c"
src = open(PATH).read()
orig = src

# 1) forward declaration: add _ffs_release_dev next to the existing decls
old_decl = "static void ffs_release_dev(struct ffs_dev *ffs_dev);"
new_decl = ("static void _ffs_release_dev(struct ffs_dev *ffs_dev);\n"
            "static void ffs_release_dev(struct ffs_dev *ffs_dev);")
assert src.count(old_decl) == 1, "forward decl not unique"
src = src.replace(old_decl, new_decl)

# 2) ffs_release_dev -> _ffs_release_dev (lock-assuming) + locking wrapper
old_rel = """static void ffs_release_dev(struct ffs_dev *ffs_dev)
{
	ffs_dev_lock();

	if (ffs_dev && ffs_dev->mounted) {
		ffs_dev->mounted = false;
		if (ffs_dev->ffs_data) {
			ffs_dev->ffs_data->private_data = NULL;
			ffs_dev->ffs_data = NULL;
		}

		if (ffs_dev->ffs_release_dev_callback)
			ffs_dev->ffs_release_dev_callback(ffs_dev);
	}

	ffs_dev_unlock();
}"""
new_rel = """/*
 * ffs_dev_lock must be taken by the caller
 */
static void _ffs_release_dev(struct ffs_dev *ffs_dev)
{
	if (ffs_dev && ffs_dev->mounted) {
		ffs_dev->mounted = false;
		if (ffs_dev->ffs_data) {
			ffs_dev->ffs_data->private_data = NULL;
			ffs_dev->ffs_data = NULL;
		}

		if (ffs_dev->ffs_release_dev_callback)
			ffs_dev->ffs_release_dev_callback(ffs_dev);
	}
}

static void ffs_release_dev(struct ffs_dev *ffs_dev)
{
	ffs_dev_lock();
	_ffs_release_dev(ffs_dev);
	ffs_dev_unlock();
}"""
assert src.count(old_rel) == 1, "ffs_release_dev body not unique"
src = src.replace(old_rel, new_rel)

# 3) ffs_free_inst: hold the lock across release + free
old_inst = """	opts = to_f_fs_opts(f);
	ffs_release_dev(opts->dev);
	ffs_dev_lock();
	_ffs_free_dev(opts->dev);
	ffs_dev_unlock();
	kfree(opts);"""
new_inst = """	opts = to_f_fs_opts(f);

	/*
	 * Release and free the dev under a single ffs_dev_lock critical
	 * section. Between ffs_release_dev() and _ffs_free_dev() the dev
	 * would still be on the ffs_devices list while already unmounted,
	 * so a concurrent ffs_acquire_dev() could link a fresh ffs_data to
	 * the doomed dev, leaving it with a dangling ->private_data that is
	 * dereferenced in ffs_closed() when that mount is torn down.
	 */
	ffs_dev_lock();
	_ffs_release_dev(opts->dev);
	_ffs_free_dev(opts->dev);
	ffs_dev_unlock();
	kfree(opts);"""
assert src.count(old_inst) == 1, "ffs_free_inst body not unique"
src = src.replace(old_inst, new_inst)

open(PATH, "w").write(src)
print("patched OK, %d bytes changed (%d -> %d)" %
      (len(src) - len(orig), len(orig), len(src)))
