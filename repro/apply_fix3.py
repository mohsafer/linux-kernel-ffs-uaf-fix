#!/usr/bin/env python3
"""v3: address Greg KH's review of v2.
1. Drop the explanatory comment in ffs_free_inst() (it duplicated the
   commit message).
2. Enforce the caller-holds-ffs_dev_lock contract of _ffs_release_dev()
   with lockdep_assert_held(&ffs_lock) instead of a comment.
3. Drop the ffs_release_dev() wrapper and its forward declaration if an
   earlier apply_fix.py run left them behind (the v2 patch state has
   neither).
Run from the top of the kernel tree on the server."""
PATH = "drivers/usb/gadget/function/f_fs.c"
src = open(PATH).read()

# 1) ffs_free_inst: remove the comment block
old = ("\topts = to_f_fs_opts(f);\n"
       "\n"
       "\t/*\n"
       "\t * Release and free the dev under a single ffs_dev_lock critical\n"
       "\t * section. Between ffs_release_dev() and _ffs_free_dev() the dev\n"
       "\t * would still be on the ffs_devices list while already unmounted,\n"
       "\t * so a concurrent ffs_acquire_dev() could link a fresh ffs_data to\n"
       "\t * the doomed dev, leaving it with a dangling ->private_data that is\n"
       "\t * dereferenced in ffs_closed() when that mount is torn down.\n"
       "\t */\n"
       "\tffs_dev_lock();\n"
       "\t_ffs_release_dev(opts->dev);\n")
new = ("\topts = to_f_fs_opts(f);\n"
       "\tffs_dev_lock();\n"
       "\t_ffs_release_dev(opts->dev);\n")
assert src.count(old) == 1, "ffs_free_inst comment block not found"
src = src.replace(old, new)

# 2) _ffs_release_dev: contract comment -> runtime enforcement
old = ("/*\n"
       " * ffs_dev_lock must be taken by the caller\n"
       " */\n"
       "static void _ffs_release_dev(struct ffs_dev *ffs_dev)\n"
       "{\n")
new = ("static void _ffs_release_dev(struct ffs_dev *ffs_dev)\n"
       "{\n"
       "\tlockdep_assert_held(&ffs_lock);\n")
assert src.count(old) == 1, "_ffs_release_dev comment not found"
src = src.replace(old, new)

# 3) drop the wrapper + stale forward declaration left by apply_fix.py
wrapper = ("\n\nstatic void ffs_release_dev(struct ffs_dev *ffs_dev)\n"
           "{\n"
           "\tffs_dev_lock();\n"
           "\t_ffs_release_dev(ffs_dev);\n"
           "\tffs_dev_unlock();\n"
           "}\n")
if wrapper in src:
    src = src.replace(wrapper, "\n", 1)
decl = "static void ffs_release_dev(struct ffs_dev *ffs_dev);\n"
if decl in src:
    src = src.replace(decl, "", 1)

# 4) normalize to the exact v3 patch formatting: blank line between the
#    lockdep assertion and the body (apply_fix.py omits it; a tree already
#    patched with the v2 mbox has it)
old = ("\tlockdep_assert_held(&ffs_lock);\n"
       "\tif (ffs_dev && ffs_dev->mounted) {\n")
new = ("\tlockdep_assert_held(&ffs_lock);\n"
       "\n"
       "\tif (ffs_dev && ffs_dev->mounted) {\n")
if old in src:
    assert src.count(old) == 1, "assertion/if spacing not unique"
    src = src.replace(old, new)

# 5) normalize the ffs_data_put() comment to the multi-line style used
#    by the v2/v3 patches (apply_fix2.py used the older one-line style)
old = ("\t\t/* ffs->private_data must be re-read under ffs_dev_lock:\n"
       "\t\t * a concurrent ffs_free_inst() may have NULLed it and freed\n"
       "\t\t * the dev it pointed to. */\n")
new = ("\t\t/*\n"
       "\t\t * ffs->private_data must be re-read under ffs_dev_lock:\n"
       "\t\t * a concurrent ffs_free_inst() may have NULLed it and\n"
       "\t\t * freed the dev it pointed to.\n"
       "\t\t */\n")
if old in src:
    assert src.count(old) == 1, "ffs_data_put comment not unique"
    src = src.replace(old, new)

open(PATH, "w").write(src)

assert src.count("lockdep_assert_held(&ffs_lock);") == 1
assert src.count("ffs_release_dev(") == src.count("_ffs_release_dev("), \
    "bare ffs_release_dev() caller remains"
print("v3 patch applied")
