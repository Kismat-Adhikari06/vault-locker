#!/usr/bin/env python3
"""
Folder locking module for VaultLock.

Uses gocryptfs (AES-256-GCM encryption via FUSE) to lock and unlock
folders. Never implements custom encryption — delegates entirely to
gocryptfs.

Locking flow:
    1. Initialize a gocryptfs cipherdir at ~/.local/share/vaultlock/vaults/<id>/
    2. Mount the cipherdir to a temporary mountpoint
    3. Move original folder contents into the mounted (encrypted) view
    4. Unmount — contents are now encrypted at rest

Unlocking flow:
    1. Mount the cipherdir to a temporary mountpoint with the user's password
    2. Move decrypted contents back to the original folder path
    3. Unmount — original folder is restored
"""

import hashlib
import os
import shutil
import signal
import stat
import subprocess
import tempfile

# Base directory for encrypted vaults
_VAULT_BASE = os.path.join(
    os.path.expanduser("~"), ".local", "share", "vaultlock", "vaults"
)


# ======================================================================
# Path helpers
# ======================================================================

def _vault_id(folder_path: str) -> str:
    """Generate a short, unique ID for a folder path using SHA-256."""
    return hashlib.sha256(folder_path.encode("utf-8")).hexdigest()[:16]


def _vault_path(folder_path: str) -> str:
    """Return the path to the encrypted vault for a given folder."""
    return os.path.join(_VAULT_BASE, _vault_id(folder_path))


def _mount_point(folder_path: str) -> str:
    """Return the temporary mount point path for a folder."""
    return os.path.join(tempfile.gettempdir(), f"vaultlock_{_vault_id(folder_path)}")


# ======================================================================
# Dependency check
# ======================================================================

def is_gocryptfs_available() -> bool:
    """Check if gocryptfs is installed on the system."""
    try:
        result = subprocess.run(
            ["which", "gocryptfs"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ======================================================================
# Status checks
# ======================================================================

def check_locked_status(folder_path: str) -> bool:
    """
    Check if a folder is currently locked.

    A folder is locked if its vault directory exists and contains
    a gocryptfs.conf file (meaning it was initialized).

    Args:
        folder_path: The absolute path of the folder.

    Returns:
        True if the folder has an initialized vault, False otherwise.
    """
    vault = _vault_path(folder_path)
    config_file = os.path.join(vault, "gocryptfs.conf")
    return os.path.isfile(config_file)


def vault_exists(folder_path: str) -> bool:
    """
    Check if a vault directory exists on disk for a folder.

    Unlike check_locked_status(), this only checks if the vault
    directory exists (regardless of whether it has gocryptfs.conf).

    Args:
        folder_path: The absolute path of the folder.

    Returns:
        True if the vault directory exists, False otherwise.
    """
    vault = _vault_path(folder_path)
    return os.path.isdir(vault)


# Keep is_locked as an alias for backward compatibility
is_locked = check_locked_status


# ======================================================================
# Password file helpers
# ======================================================================

def _write_password_file(password: str) -> str:
    """
    Write a password to a temporary file with restrictive permissions (0o600).

    Args:
        password: The password string to write.

    Returns:
        The path to the temporary password file.
    """
    fd, path = tempfile.mkstemp(prefix="vaultlock_pw_")
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        os.write(fd, password.encode("utf-8"))
    finally:
        os.close(fd)
    return path


def _remove_password_file(path: str):
    """Securely remove a temporary password file."""
    try:
        os.unlink(path)
    except OSError:
        pass


# ======================================================================
# Permission management
# ======================================================================

def _save_permissions(folder_path: str, vault_path: str):
    """
    Save the original folder permissions to a metadata file in the vault.

    Args:
        folder_path: The folder whose permissions to save.
        vault_path: The vault directory to store metadata in.
    """
    mode = os.stat(folder_path).st_mode & 0o7777  # permission bits only
    meta_path = os.path.join(vault_path, ".vaultlock_perms")
    with open(meta_path, "w") as f:
        f.write(str(mode))


def _load_permissions(vault_path: str) -> int:
    """
    Load the original folder permissions from vault metadata.

    Args:
        vault_path: The vault directory containing metadata.

    Returns:
        The original permission mode, or 0o755 if not found.
    """
    meta_path = os.path.join(vault_path, ".vaultlock_perms")
    try:
        with open(meta_path, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0o755  # default


def _kill_folder_processes(folder_path: str):
    """
    Kill any processes that have files open in the given folder.

    This prevents viewers/players from continuing to access files
    after they are moved into the encrypted vault during locking.

    Uses lsof -t +D to get PIDs with open file handles,
    then sends SIGTERM to each (excluding our own process).
    Falls back to SIGKILL if SIGTERM doesn't work within 1 second.

    Args:
        folder_path: The folder whose open-file processes to kill.
    """
    current_pid = os.getpid()

    try:
        # -t outputs only PIDs (one per line), avoids parsing issues
        # with multi-word command names like "GNOME Videos"
        # NOTE: lsof returns non-zero when it finds matches, so we
        # check stdout first rather than the return code.
        result = subprocess.run(
            ["lsof", "-t", "+D", folder_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if not result.stdout.strip():
            return  # No processes found

        pids = set()
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                pid = int(line)
                if pid != current_pid:
                    pids.add(pid)
            except ValueError:
                continue

        if not pids:
            return

        print(f"[VaultLock] Found {len(pids)} process(es) with open files: {pids}")

        # First try SIGTERM (graceful shutdown)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"[VaultLock] Sent SIGTERM to process {pid}")
            except (OSError, ProcessLookupError):
                pass

        # Wait for processes to terminate
        import time
        time.sleep(1.0)

        # If any are still alive, force kill with SIGKILL
        for pid in pids:
            try:
                os.kill(pid, 0)  # Check if still alive
                os.kill(pid, signal.SIGKILL)
                print(f"[VaultLock] Sent SIGKILL to process {pid}")
            except (OSError, ProcessLookupError):
                pass

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # lsof not installed or timed out — skip gracefully


def _lock_permissions(folder_path: str):
    """
    Make a folder read-only (chmod 555) to prevent writes while locked.

    Args:
        folder_path: The folder to make read-only.
    """
    os.chmod(folder_path, 0o555)


def _unlock_permissions(folder_path: str, vault_path: str):
    """
    Restore original folder permissions after unlocking.

    Args:
        folder_path: The folder to restore permissions on.
        vault_path: The vault directory to read metadata from.
    """
    original_mode = _load_permissions(vault_path)
    os.chmod(folder_path, original_mode)


def create_vault(folder_path: str, password: str) -> str:
    """
    Create an encrypted gocryptfs vault for a folder.

    This only creates and initializes the vault — it does NOT move
    any files. Use lock_folder() for the complete lock workflow.

    Args:
        folder_path: The absolute path of the folder.
        password: The password to encrypt the vault with.

    Returns:
        The path to the created vault directory.

    Raises:
        RuntimeError: If gocryptfs is not installed or init fails.
    """
    if not is_gocryptfs_available():
        raise RuntimeError(
            "gocryptfs is not installed. Install it before using folder locking.\n"
            "  Ubuntu/Debian: sudo apt install gocryptfs\n"
            "  Fedora:        sudo dnf install gocryptfs\n"
            "  Arch:          sudo pacman -S gocryptfs"
        )

    vault = _vault_path(folder_path)

    # Create vault directory
    os.makedirs(vault, exist_ok=True)

    # Initialize gocryptfs with the password
    pw_file = _write_password_file(password)
    try:
        result = subprocess.run(
            ["gocryptfs", "-init", "-passfile", pw_file, "-q", vault],
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        _remove_password_file(pw_file)

    if result.returncode != 0:
        shutil.rmtree(vault, ignore_errors=True)
        raise RuntimeError(f"gocryptfs init failed: {result.stderr.strip()}")

    return vault


def lock_folder(folder_path: str, password: str) -> str:
    """
    Lock a folder by moving its contents into an encrypted gocryptfs vault.

    Steps:
        1. Check folder exists and is not already locked
        2. Create and initialize the vault
        3. Mount the vault via FUSE
        4. Move original folder contents into the mounted vault
        5. Unmount — contents are now AES-256-GCM encrypted at rest

    Args:
        folder_path: The absolute path of the folder to lock.
        password: The user's password (used to derive encryption key).

    Returns:
        A success message.

    Raises:
        FileNotFoundError: If the folder doesn't exist.
        RuntimeError: If gocryptfs is not installed or operations fail.
        ValueError: If the folder is already locked or empty.
    """
    # --- Precondition checks ---
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if is_locked(folder_path):
        raise ValueError("Folder is already locked")

    # Check if folder has any contents
    contents = os.listdir(folder_path)
    if not contents:
        raise ValueError("Folder is empty — nothing to lock")

    vault = _vault_path(folder_path)
    mount = _mount_point(folder_path)

    try:
        # Step 1: Create and initialize the vault
        create_vault(folder_path, password)

        # Step 2: Mount the vault via FUSE
        os.makedirs(mount, exist_ok=True)

        pw_file = _write_password_file(password)
        try:
            result = subprocess.run(
                ["gocryptfs", "-passfile", pw_file, "-q", vault, mount],
                capture_output=True,
                text=True,
                timeout=15,
            )
        finally:
            _remove_password_file(pw_file)

        if result.returncode != 0:
            shutil.rmtree(vault, ignore_errors=True)
            raise RuntimeError(f"gocryptfs mount failed: {result.stderr.strip()}")

        # Step 2.5: Kill any processes with files open in the folder
        # This prevents viewers/players from keeping access to files
        # after they are moved into the encrypted vault.
        _kill_folder_processes(folder_path)

        # Step 3: Move original contents into the mounted vault
        for item in os.listdir(folder_path):
            src = os.path.join(folder_path, item)
            dst = os.path.join(mount, item)
            shutil.move(src, dst)

        # Step 4: Unmount — contents are now encrypted at rest
        _unmount(mount)

        # Step 5: Save original permissions and make folder read-only
        _save_permissions(folder_path, vault)
        _lock_permissions(folder_path)

        return "Folder locked successfully"

    except Exception:
        # Cleanup on any failure
        _unmount(mount)
        shutil.rmtree(mount, ignore_errors=True)
        raise


def unlock_folder(folder_path: str, password: str) -> str:
    """
    Unlock a folder by decrypting its vault and restoring contents.

    Steps:
        1. Mount the vault with the password (decrypts on-the-fly)
        2. Move decrypted contents back to original folder path
        3. Unmount the vault
        4. Remove the vault (data is now in plaintext at original location)

    Args:
        folder_path: The absolute path where the folder should be restored.
        password: The user's password (to decrypt the vault).

    Returns:
        A success message.

    Raises:
        RuntimeError: If gocryptfs fails (e.g., wrong password).
        ValueError: If the folder is not locked.
    """
    if not is_locked(folder_path):
        raise ValueError("Folder is not locked")

    vault = _vault_path(folder_path)
    mount = _mount_point(folder_path)

    try:
        os.makedirs(mount, exist_ok=True)

        # Step 0: Restore folder permissions so we can write to it
        _unlock_permissions(folder_path, vault)

        # Step 1: Mount the vault with password
        pw_file = _write_password_file(password)
        try:
            result = subprocess.run(
                ["gocryptfs", "-passfile", pw_file, "-q", vault, mount],
                capture_output=True,
                text=True,
                timeout=15,
            )
        finally:
            _remove_password_file(pw_file)

        if result.returncode != 0:
            _cleanup_mount(mount)
            # Exit code 12 = wrong password in gocryptfs
            if result.returncode == 12:
                raise RuntimeError("Wrong password")
            raise RuntimeError(f"gocryptfs mount failed: {result.stderr.strip()}")

        # Step 2: Move decrypted contents back to original path
        os.makedirs(folder_path, exist_ok=True)

        for item in os.listdir(mount):
            src = os.path.join(mount, item)
            dst = os.path.join(folder_path, item)
            shutil.move(src, dst)

        # Step 3: Unmount
        _unmount(mount)

        # Step 4: Remove vault (files are now plaintext at original location)
        shutil.rmtree(vault, ignore_errors=True)

        return "Folder unlocked successfully"

    except Exception:
        _cleanup_mount(mount)
        raise


def change_password(folder_path: str, old_password: str, new_password: str) -> str:
    """
    Change the password for a locked folder's vault.

    Uses gocryptfs -passwd to re-encrypt the vault key with the new password.
    The actual file contents are NOT re-encrypted — only the master key wrapper
    is updated.

    Args:
        folder_path: The absolute path of the locked folder.
        old_password: The current password.
        new_password: The new password to set.

    Returns:
        A success message.

    Raises:
        RuntimeError: If gocryptfs fails (e.g., wrong old password).
        ValueError: If the folder is not locked.
    """
    if not is_locked(folder_path):
        raise ValueError("Folder is not locked")

    vault = _vault_path(folder_path)

    # Pipe old and new passwords to gocryptfs -passwd
    password_input = f"{old_password}\n{new_password}\n"

    result = subprocess.run(
        ["gocryptfs", "-passwd", vault],
        input=password_input,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "Decrypting master key" in stderr or "wrong" in stderr.lower():
            raise RuntimeError("Wrong password")
        raise RuntimeError(f"Password change failed: {stderr}")

    return "Password changed successfully"


# ======================================================================
# Internal helpers
# ======================================================================

def _unmount(mount_point: str):
    """Unmount a FUSE mount point."""
    if os.path.ismount(mount_point):
        subprocess.run(
            ["fusermount", "-u", mount_point],
            capture_output=True,
            timeout=10,
        )
    # Clean up mount directory
    try:
        os.rmdir(mount_point)
    except OSError:
        pass


def _cleanup_mount(mount_point: str):
    """Unmount and clean up a mount point, ignoring errors."""
    _unmount(mount_point)
    shutil.rmtree(mount_point, ignore_errors=True)
