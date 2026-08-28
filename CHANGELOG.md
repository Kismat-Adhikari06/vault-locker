# Changelog

All notable changes to VaultLock will be documented in this file.

## [0.1.0] - 2025-08-28

### Added
- Initial release with GTK4 + libadwaita interface
- Folder selection with GTK4 FileDialog
- Persistent JSON storage
- Password management with bcrypt hashing
- Folder locking with gocryptfs (AES-256-GCM)
- Lock/unlock flow with confirmation dialogs
- Loading states during encryption/decryption
- Startup folder verification
- Refresh button for status updates
- Missing folder detection
- State reconciliation for stale vaults
- CLI argument support for folder path
- File manager integration (Nautilus, Nemo, Dolphin)
- Desktop entry for app registration

### Fixed
- Adw version string compatibility
- ApplicationFlags for Gio
- set_content vs set_child for AdwApplicationWindow
- PasswordEntry placeholder_text compatibility
- ResponseAppearance.DESTRUCTIVE for error dialogs

### Security
- Passwords bcrypt-hashed, never stored in plain text
- gocryptfs handles all encryption (no custom crypto)
- Temporary password files with restrictive permissions (0o600)
- Constant-time password comparison via bcrypt
