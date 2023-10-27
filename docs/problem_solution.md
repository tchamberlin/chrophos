# Problems/Solutions

## Canon EOS 5D Mark II

### *** Error (-53: 'Could not claim the USB device') ***

Disabled these two, per https://github.com/gphoto/gphoto2/issues/181:
```sh
sudo chmod -x /usr/lib/gvfs/gvfsd-gphoto2
sudo chmod -x /usr/lib/gvfs/gvfs-gphoto2-volume-monitor
```

Also, this seems to help reclaim the USB device:

```sh
gio mount -s gphoto2
```

### Full Release Failed

*** Error ***
Canon EOS Full-Release failed (0x02ff: PTP I/O Error)
ERROR: Could not capture image.
ERROR: Could not capture.
