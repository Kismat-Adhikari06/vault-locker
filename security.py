#!/usr/bin/env python3
"""
Security module for VaultLock.

Handles password hashing and verification using bcrypt.
Passwords are never stored in plain text — only salted hashes.

bcrypt is used because:
- It's designed for password hashing (not general-purpose hashing)
- It includes a random salt per password
- It's computationally slow by design (brute-force resistant)
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with a random salt.

    Args:
        password: The plain-text password to hash.

    Returns:
        A bcrypt hash string (includes salt) safe to store in JSON.
    """
    # Encode the password to bytes (bcrypt requires bytes)
    password_bytes = password.encode("utf-8")

    # Generate a salt and hash the password
    # rounds=12 is the default cost factor (good balance of speed/security)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as a UTF-8 string for JSON storage
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against a stored bcrypt hash.

    Args:
        password: The plain-text password to check.
        password_hash: The stored bcrypt hash string.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        password_bytes = password.encode("utf-8")
        hash_bytes = password_hash.encode("utf-8")

        # bcrypt.checkpw handles salt extraction and constant-time comparison
        return bcrypt.checkpw(password_bytes, hash_bytes)

    except (ValueError, TypeError):
        # Invalid hash format or encoding error
        return False


def verify_folder_password(folder_path: str, password: str) -> bool:
    """
    Verify a password for a specific folder.

    Loads the folder's stored hash from the JSON file and checks
    the provided password against it.

    Args:
        folder_path: The absolute path of the folder.
        password: The password to verify.

    Returns:
        True if the password is correct, False otherwise.
    """
    from storage import FolderStorage

    storage = FolderStorage()
    folders = storage.load_folder_entries()

    # Find the entry for this folder
    for entry in folders:
        if entry.get("path") == folder_path:
            stored_hash = entry.get("password_hash", "")
            if not stored_hash:
                # No password set — consider it "unlocked"
                return True
            return verify_password(password, stored_hash)

    # Folder not found
    return False
