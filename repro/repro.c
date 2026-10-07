// SPDX-License-Identifier: GPL-2.0
/*
 * Reproducer for: KASAN: slab-use-after-free Write in ffs_data_clear
 * syzbot extid=6227549bd2c8a1ec8ba0
 *
 * Bug (analysis): ffs_free_inst() (drivers/usb/gadget/function/f_fs.c)
 * releases the ffs_dev (ffs_release_dev: mounted=false, unlink) and then
 * re-acquires ffs_dev_lock only for _ffs_free_dev(). In the window the
 * struct ffs_dev is still on the global ffs_devices list, unmounted, with
 * its name intact -- so a concurrent mount(2) of functionfs succeeds in
 * ffs_acquire_dev() and links a fresh ffs_data to the doomed dev
 * (ffs_data->private_data = dev). _ffs_free_dev() then kfrees the dev.
 * When that mount is later torn down (umount -> ffs_fs_kill_sb ->
 * ffs_data_reset -> ffs_data_clear -> ffs_closed), ffs_closed() writes
 * ffs_obj->desc_ready = false into the freed ffs_dev.
 *
 * Usage: repro [seconds]   (default 45)
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <pthread.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/wait.h>

#define CFG_ROOT	"/sys/kernel/config"
#define GADGET_DIR	CFG_ROOT "/usb_gadget/g1"
#define FN_ROOT		GADGET_DIR "/functions"
#define INST_DIR	FN_ROOT "/ffs.f0"
#define NAME		"f0"
#define NMNT		4

static const char *mntpoints[NMNT] = {
	"/mnt/ffs0", "/mnt/ffs1", "/mnt/ffs2", "/mnt/ffs3"
};

static volatile int stop_flag;
static volatile long n_mount_ok, n_mount_err, n_umount, n_mkdir, n_rmdir;

static int xmkdir(const char *path)
{
	return mkdir(path, 0755);	/* EEXIST is fine */
}

static void rand_us(void)
{
	usleep(rand() % 300);
}

static void *mounter(void *arg)
{
	long id = (long)arg;

	while (!stop_flag) {
		if (mount(NAME, mntpoints[id], "functionfs", 0, NULL) == 0) {
			__sync_fetch_and_add(&n_mount_ok, 1);
			if (rand() % 4 == 0)
				rand_us();	/* hold the mount briefly */
			if (umount2(mntpoints[id], MNT_DETACH) == 0)
				__sync_fetch_and_add(&n_umount, 1);
		} else {
			__sync_fetch_and_add(&n_mount_err, 1);
			rand_us();
		}
	}
	return NULL;
}

static void *remover(void *arg)
{
	while (!stop_flag) {
		if (rmdir(INST_DIR) == 0)
			__sync_fetch_and_add(&n_rmdir, 1);
		rand_us();
		if (xmkdir(INST_DIR) == 0)
			__sync_fetch_and_add(&n_mkdir, 1);
		rand_us();
	}
	return NULL;
}

int main(int argc, char **argv)
{
	int secs = argc > 1 ? atoi(argv[1]) : 45;
	pthread_t th[NMNT + 2];
	int i, err;
	char buf[256];

	srand(getpid());
	setvbuf(stdout, NULL, _IOLBF, 0);

	/* make sure configfs is mounted */
	if (mount("none", CFG_ROOT, "configfs", 0, NULL) && errno != EBUSY) {
		fprintf(stderr, "mount configfs: %s\n", strerror(errno));
		return 1;
	}
	for (i = 0; i < NMNT; i++)
		xmkdir(mntpoints[i]);

	/* create gadget skeleton: usb_gadget/g1/functions/ffs.f0 */
	if (xmkdir(GADGET_DIR) && errno != EEXIST) {
		fprintf(stderr, "mkdir %s: %s (usb_gadget registered?)\n",
			GADGET_DIR, strerror(errno));
		return 1;
	}
	xmkdir(FN_ROOT);		/* auto-created, just in case */
	if (xmkdir(INST_DIR) && errno != EEXIST) {
		fprintf(stderr, "mkdir %s: %s\n", INST_DIR, strerror(errno));
		return 1;
	}
	snprintf(buf, sizeof(buf), "setup ok: instance %s created\n", INST_DIR);
	write(1, buf, strlen(buf));

	for (i = 0; i < 2; i++) {
		err = pthread_create(&th[i], NULL, remover, NULL);
		if (err) {
			perror("pthread_create remover");
			return 1;
		}
	}
	for (i = 2; i < NMNT + 2; i++) {
		err = pthread_create(&th[i], NULL, mounter,
				     (void *)(long)(i - 2));
		if (err) {
			perror("pthread_create mounter");
			return 1;
		}
	}

	sleep(secs);
	stop_flag = 1;
	for (i = 0; i < NMNT + 2; i++)
		pthread_join(th[i], NULL);

	/* clean up what we can; ignore errors */
	umount2("/mnt/ffs0", MNT_DETACH);
	umount2("/mnt/ffs1", MNT_DETACH);
	umount2("/mnt/ffs2", MNT_DETACH);
	umount2("/mnt/ffs3", MNT_DETACH);
	rmdir(INST_DIR);
	rmdir(GADGET_DIR);

	printf("stats: mount_ok=%ld mount_err=%ld umount=%ld mkdir=%ld rmdir=%ld\n",
	       n_mount_ok, n_mount_err, n_umount, n_mkdir, n_rmdir);
	printf("repro finished without killing the box\n");
	return 0;
}
