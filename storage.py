#!/usr/bin/env python3
"""
Persistent storage module for VaultLock.

Manages saving, loading, and removing folder entries
in a local JSON file at ~/.config/vaultlock/folders.json.
"""

import json
import os

_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "vaultlock")
_DATA_FILE = os.path.join(_CONFIG_DIR, "folders.json")


class FolderStorage:
    """Handles persistent storage of folder entries using a local JSON file."""

    def __init__(self):
        os.makedirs(_CONFIG_DIR, exist_ok=True)

    def load_folders(self) -> list[str]:
        if not os.path.exists(_DATA_FILE):
            return []
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [entry["path"] for entry in data.get("folders", [])]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

    def save_folders(self, folder_paths: list[str]):
        data = {"folders": [{"path": p} for p in folder_paths]}
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def add_folder(self, folder_path: str, existing_paths: list[str]) -> list[str]:
        if folder_path not in existing_paths:
            existing_paths.append(folder_path)
            self.save_folders(existing_paths)
        return existing_paths

    def remove_folder(self, folder_path: str, existing_paths: list[str]) -> list[str]:
        if folder_path in existing_paths:
            existing_paths.remove(folder_path)
            self.save_folders(existing_paths)
        return existing_paths

    @staticmethod
    def get_storage_path() -> str:
        return _DATA_FILE
