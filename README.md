# VaultLock

A lightweight folder locking application for Linux desktops, built with modern GNOME technologies.

## Description

VaultLock provides a simple, clean interface for managing folder security on Linux. It uses **gocryptfs** (AES-256-GCM encryption via FUSE) to securely lock and unlock folders with a password.

- **Lightweight** — Minimal resource usage
- **Modern** — Built with GTK4 and libadwaita for a native GNOME look and feel
- **Secure** — Uses gocryptfs for industry-standard encryption (no custom crypto)

## Features

- Add/remove folders from the lock list
- Set passwords per folder (bcrypt-hashed, never stored in plain text)
- **Lock folders** — encrypts contents into an encrypted vault
- **Unlock folders** — decrypts and restores contents
- Persistent storage — folders and passwords survive app restarts
- Startup verification — detects missing folders and stale vault states
- Refresh button — recheck all folder statuses on demand
- Missing folder handling — offers to remove entries for deleted folders
- State reconciliation — automatically corrects inconsistent lock states

## Dependencies

| Package | Description |
|---------|-------------|
| Python 3.10+ | Python interpreter |
| GTK 4.0 | GNOME GUI toolkit |
| libadwaita 1.0 | Modern GNOME styling library |
| PyGObject | Python bindings for GLib/GTK |
| bcrypt | Password hashing (Python package) |
| **gocryptfs** | Encrypted filesystem (AES-256-GCM via FUSE) |
| fuse3 | Filesystem in Userspace |

### Installing Dependencies

#### Ubuntu / Debian

```bash
sudo apt install gocryptfs fuse3 libgtk-4-dev libadwaita-1-dev python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
pip install bcrypt
```

#### Fedora

```bash
sudo dnf install gocryptfs fuse3 gtk4 libadwaita python3-gobject python3-bcrypt
```

#### Arch Linux

```bash
sudo pacman -S gocryptfs fuse3 gtk4 libadwaita python-gobject python-bcrypt
```

## Running

```bash
cd vaultlock
python3 main.py
```

With a folder path (for file manager integration):

```bash
python3 main.py /path/to/folder
```

## Project Structure

```
vaultlock/
├── main.py              # Application entry point, CLI argument handling
├── window.py            # Main window, folder list, dialogs
├── folder_item.py       # Reusable folder row widget
├── storage.py           # JSON persistence (~/.config/vaultlock/)
├── security.py          # bcrypt password hashing/verification
├── locker.py            # gocryptfs lock/unlock operations
├── vaultlock.desktop    # Desktop entry for app registration
├── integration/         # File manager right-click integration
│   ├── install.sh       # Auto-installer for detected file managers
│   ├── nautilus/        # Nautilus/Nemo script
│   └── dolphin/         # KDE Dolphin service menu
└── README.md
```

## How It Works

### Locking

```
Original folder: ~/Documents/
    ├── file1.txt
    └── photo.png

        ↓ User clicks Lock → enters password

Encrypted vault: ~/.local/share/vaultlock/vaults/<hash>/
    ├── gocryptfs.conf
    └── <encrypted files>

Original folder: ~/Documents/  (empty)
```

### Unlocking

```
Encrypted vault exists

        ↓ User clicks Unlock → enters password

Vault is mounted via FUSE (decrypts on-the-fly)
    ↓
Files moved back to original folder
    ↓
Vault is removed
```

### Password Storage

Passwords are bcrypt-hashed and stored in `~/.config/vaultlock/folders.json`:

```json
{
    "folders": [
        {
            "path": "/home/user/Documents",
            "locked": false,
            "password_hash": "$2b$12$...",
            "vault_path": "",
            "created": "2025-01-15T10:30:00+00:00"
        }
    ]
}
```

## Data Locations

| What | Where |
|------|-------|
| App config | `~/.config/vaultlock/folders.json` |
| Encrypted vaults | `~/.local/share/vaultlock/vaults/<hash>/` |

## File Manager Integration

VaultLock supports right-click integration with Nautilus, Nemo, and Dolphin.

```bash
cd integration
chmod +x install.sh
./install.sh
```

Then right-click any folder → **"Lock with VaultLock"**.

## Testing

1. Create a test folder: `mkdir -p ~/VaultTest && echo "test" > ~/VaultTest/test.txt`
2. Run VaultLock: `python3 main.py`
3. Add folder → Set Password → Lock
4. Check folder is empty: `ls ~/VaultTest`
5. Unlock → Verify files are back: `cat ~/VaultTest/test.txt`

## License

This project is open source.
