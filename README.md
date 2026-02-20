# MacBook Pro to MacBook Air SSHFS Mount Instructions

To mount the `/Volumes/iPad_DOK` directory from your MacBook Air (192.168.1.78) onto your MacBook Pro (192.168.1.88), use the following commands:

## Mount Command (on MacBook Pro)
```bash
sshfs admin@192.168.1.78:/Volumes/iPad_DOK ~/local_dok -o auto_cache,reconnect,volname=iPad_DOK
```

## Unmount Command (on MacBook Pro)
```bash
umount ~/local_dok
```
If the directory is busy, use:
```bash
diskutil unmount force ~/local_dok
```

## Check Mount Status
```bash
df -h | grep local_dok
```

**Note:** Ensure 'Remote Login' is enabled in System Settings (General > Sharing > Remote Login) on the MacBook Air. Passwordless SSH is already set up for your MacBook Pro's `id_ed25519.pub` key.
