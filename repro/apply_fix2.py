#!/usr/bin/env python3
"""v2: close the TOCTOU read of ffs->private_data in ffs_data_put().
Run from the top of the kernel tree on the server."""
PATH = "drivers/usb/gadget/function/f_fs.c"
src = open(PATH).read()

old = "\t\tffs_data_clear(ffs);\n\t\tffs_release_dev(ffs->private_data);\n"
new = ("\t\tffs_data_clear(ffs);\n"
       "\t\t/* ffs->private_data must be re-read under ffs_dev_lock:\n"
       "\t\t * a concurrent ffs_free_inst() may have NULLed it and freed\n"
       "\t\t * the dev it pointed to. */\n"
       "\t\tffs_dev_lock();\n"
       "\t\t_ffs_release_dev(ffs->private_data);\n"
       "\t\tffs_dev_unlock();\n")
assert src.count(old) == 1, "ffs_data_put release line not unique"
src = src.replace(old, new)
open(PATH, "w").write(src)
print("v2 patch applied")
