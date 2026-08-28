#!/usr/bin/env python3
"""
Persistent storage module for VaultLock.

Manages saving, loading, and removing folder entries
in a local JSON file at ~/.config/vaultlock/folders.json.

Each folder entry has this format:
{
    "path": "/home/user/Documents",
    "locked": false,
    "password_hash": "",
    "vault_path": ""
}
"""

import json
import os
from datetime import datetime, timezone

# Default storage location
_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "vaultlock")
_DATA_FILE = os.path.join(_CONFIG_DIR, "folders.json")


class FolderStorage:
    """
    Handles persistent storage of folder entries using a local JSON file.

    Data is stored at ~/.config/vaultlock/folders.json with this format:
    {
        "folders": [
            {
                "path": "/home/user/Documents",
                "locked": false,
                "password_hash": "",
                "vault_path": ""
            }
        ]
    }
    """

    def __init__(self):
        """Initialize storage and ensure the config directory exists."""
        os.makedirs(_CONFIG_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_folders(self) -> list[str]:
        """
        Load all saved folder paths from the JSON file.

        Returns:
            A list of folder path strings. Returns an empty list
            if the file doesn't exist or is invalid.
        """
        entries = self.load_folder_entries()
        return [entry["path"] for entry in entries]

    def load_folder_entries(self) -> list[dict]:
        """
        Load all saved folder entries (full dictionaries) from the JSON file.

        Returns:
            A list of dicts, each with "path", "locked", "password_hash", "vault_path".
            Returns an empty list if the file doesn't exist or is invalid.
        """
        if not os.path.exists(_DATA_FILE):
            return []

        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            entries = data.get("folders", [])

            # Ensure each entry has the required fields (backward compat)
            result = []
            for entry in entries:
                result.append({
                    "path": entry.get("path", ""),
                    "locked": entry.get("locked", False),
                    "password_hash": entry.get("password_hash", ""),
                    "vault_path": entry.get("vault_path", ""),
                    "created": entry.get("created", ""),
                })

            return result

        except (json.JSONDecodeError, KeyError, TypeError):
            return []

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save_folders(self, folder_paths: list[str]):
        """
        Save the complete list of folder paths to the JSON file.

        Preserves existing locked/password_hash/vault_path fields for folders
        that are already in the file.

        Args:
            folder_paths: List of absolute folder path strings.
        """
        # Load existing entries to preserve password/vault data
        existing = {e["path"]: e for e in self.load_folder_entries()}

        folders = []
        for path in folder_paths:
            if path in existing:
                # Keep the existing entry (with password_hash, vault_path, etc.)
                folders.append(existing[path])
            else:
                # New folder — start with defaults
                folders.append({
                    "path": path,
                    "locked": False,
                    "password_hash": "",
                    "vault_path": "",
                    "created": datetime.now(timezone.utc).isoformat(),
                })

        data = {"folders": folders}

        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def save_folder_entries(self, entries: list[dict]):
        """
        Save the complete list of folder entries (full dicts) to the JSON file.

        Args:
            entries: List of dicts with "path", "locked", "password_hash", "vault_path".
        """
        data = {"folders": entries}

        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    # ------------------------------------------------------------------
    # Adding / Removing
    # ------------------------------------------------------------------

    def add_folder(self, folder_path: str, existing_paths: list[str]) -> list[str]:
        """
        Add a folder path and save immediately.

        Args:
            folder_path: The absolute path to add.
            existing_paths: The current list of saved paths.

        Returns:
            The updated list of paths (with the new one appended).
        """
        if folder_path not in existing_paths:
            existing_paths.append(folder_path)
            self.save_folders(existing_paths)

        return existing_paths

    def remove_folder(self, folder_path: str, existing_paths: list[str]) -> list[str]:
        """
        Remove a folder path and save immediately.

        Args:
            folder_path: The absolute path to remove.
            existing_paths: The current list of saved paths.

        Returns:
            The updated list of paths (with the entry removed).
        """
        if folder_path in existing_paths:
            existing_paths.remove(folder_path)
            self.save_folders(existing_paths)

        return existing_paths

    # ------------------------------------------------------------------
    # Updating individual entries
    # ------------------------------------------------------------------

    def update_folder_password(self, folder_path: str, password_hash: str, locked: bool = True):
        """
        Update the password hash and lock status for a specific folder.

        Args:
            folder_path: The absolute path of the folder.
            password_hash: The bcrypt hash string to store.
            locked: Whether the folder is now locked.
        """
        entries = self.load_folder_entries()

        for entry in entries:
            if entry["path"] == folder_path:
                entry["password_hash"] = password_hash
                entry["locked"] = locked
                break

        self.save_folder_entries(entries)

    def update_lock_status(self, folder_path: str, locked: bool):
        """
        Update only the lock status and vault_path for a specific folder.

        Args:
            folder_path: The absolute path of the folder.
            locked: Whether the folder is now locked.
        """
        entries = self.load_folder_entries()

        for entry in entries:
            if entry["path"] == folder_path:
                entry["locked"] = locked
                # Auto-set vault_path based on lock state
                if locked:
                    from locker import _vault_path
                    entry["vault_path"] = _vault_path(folder_path)
                else:
                    entry["vault_path"] = ""
                break

        self.save_folder_entries(entries)

    @staticmethod
    def get_storage_path() -> str:
        """Return the path to the JSON data file."""
        return _DATA_FILE
