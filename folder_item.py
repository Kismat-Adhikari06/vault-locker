#!/usr/bin/env python3
"""
Reusable folder list item component for VaultLock.

Each item displays:
- A folder or lock icon (based on lock status)
- The folder's display name (basename)
- Status text: "Locked", "Unlocked", "Missing", "Loading..."
- Action buttons: Lock, Unlock, Set Password, Remove
- Loading spinner during lock/unlock operations

Extends Gtk.ListBoxRow so it can be used directly in a Gtk.ListBox.
"""

import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GObject, Gtk


class FolderItem(Gtk.ListBoxRow):
    """
    A list row widget representing a single folder.

    Shows different UI states based on lock and password status:
    - Unlocked + no password: "Set Password" and "Lock" buttons
    - Unlocked + has password: "Lock" button only
    - Locked: "Unlock" button only
    - Missing: "Remove" button only (folder not found on disk)
    - Loading: spinner + "Locking..." / "Unlocking..."

    Signals:
        remove-request (str): Emitted when remove is clicked.
        password-request (str): Emitted when "Set Password" is clicked.
        lock-request (str): Emitted when "Lock" is clicked.
        unlock-request (str): Emitted when "Unlock" is clicked.
    """

    __gsignals__ = {
        "remove-request": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "password-request": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "lock-request": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "unlock-request": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, folder_path: str, has_password: bool = False,
                 locked: bool = False, missing: bool = False):
        super().__init__()

        self._folder_path = folder_path
        self._has_password = has_password
        self._locked = locked
        self._missing = missing
        self._loading = False
        self._loading_message = ""

        # Extract the folder name
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path
        self._folder_name = folder_name

        self._build_ui()

    def _build_ui(self):
        """Construct the row's widget tree."""
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row_box.set_margin_top(8)
        row_box.set_margin_bottom(8)
        row_box.set_margin_start(12)
        row_box.set_margin_end(12)

        # --- Icon (changes based on lock state) ---
        self._icon = Gtk.Image()
        self._update_icon()
        row_box.append(self._icon)

        # --- Text container ---
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        # Folder name
        name_label = Gtk.Label(label=self._folder_name)
        name_label.set_xalign(0)
        name_label.add_css_class("heading")
        name_label.set_ellipsize(3)
        text_box.append(name_label)

        # Status text
        self._status_label = Gtk.Label()
        self._status_label.set_xalign(0)
        self._status_label.add_css_class("caption")
        self._status_label.add_css_class("dim-label")
        self._status_label.set_ellipsize(3)
        self._update_status_text()
        text_box.append(self._status_label)

        row_box.append(text_box)

        # --- Action buttons ---
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        # Set Password button
        self._password_button = Gtk.Button(label="Set Password")
        self._password_button.add_css_class("flat")
        self._password_button.add_css_class("circular")
        self._password_button.set_tooltip_text("Set a password for this folder")
        self._password_button.connect("clicked", self._on_password_clicked)
        buttons_box.append(self._password_button)

        # Lock button
        self._lock_button = Gtk.Button(label="Lock")
        self._lock_button.add_css_class("destructive-action")
        self._lock_button.add_css_class("circular")
        self._lock_button.set_tooltip_text("Encrypt and lock this folder")
        self._lock_button.connect("clicked", self._on_lock_clicked)
        buttons_box.append(self._lock_button)

        # Unlock button
        self._unlock_button = Gtk.Button(label="Unlock")
        self._unlock_button.add_css_class("suggested-action")
        self._unlock_button.add_css_class("circular")
        self._unlock_button.set_tooltip_text("Decrypt and unlock this folder")
        self._unlock_button.connect("clicked", self._on_unlock_clicked)
        buttons_box.append(self._unlock_button)

        # Remove button
        remove_button = Gtk.Button(icon_name="user-trash-symbolic")
        remove_button.add_css_class("flat")
        remove_button.add_css_class("circular")
        remove_button.set_tooltip_text("Remove folder")
        remove_button.connect("clicked", self._on_remove_clicked)
        buttons_box.append(remove_button)

        row_box.append(buttons_box)

        self.set_child(row_box)

        # Apply initial button visibility
        self._update_button_visibility()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def folder_path(self) -> str:
        return self._folder_path

    def set_password_set(self):
        """Update UI to reflect that a password has been set."""
        self._has_password = True
        self._missing = False
        self._update_icon()
        self._update_status_text()
        self._update_button_visibility()

    def set_locked(self):
        """Update UI to reflect that the folder is now locked."""
        self._locked = True
        self._missing = False
        self._loading = False
        self._update_icon()
        self._update_status_text()
        self._update_button_visibility()

    def set_unlocked(self):
        """Update UI to reflect that the folder is now unlocked."""
        self._locked = False
        self._missing = False
        self._loading = False
        self._update_icon()
        self._update_status_text()
        self._update_button_visibility()

    def set_missing(self):
        """Update UI to reflect that the folder no longer exists on disk."""
        self._missing = True
        self._loading = False
        self._update_icon()
        self._update_status_text()
        self._update_button_visibility()

    def set_exists(self):
        """Update UI to reflect that a previously missing folder exists again."""
        self._missing = False
        self._update_icon()
        self._update_status_text()
        self._update_button_visibility()

    def set_loading(self, loading: bool, message: str = ""):
        """
        Show or hide loading state.

        Args:
            loading: True to show loading, False to hide.
            message: Optional message like "Locking..." or "Unlocking..."
        """
        self._loading = loading
        self._loading_message = message
        self._update_status_text()
        self._update_button_visibility()

    # ------------------------------------------------------------------
    # Internal updates
    # ------------------------------------------------------------------

    def _update_icon(self):
        if self._loading:
            icon_name = "content-loading-symbolic"
        elif self._missing:
            icon_name = "dialog-warning-symbolic"
        elif self._locked:
            icon_name = "changes-prevent-symbolic"
        else:
            icon_name = "folder-symbolic"

        self._icon.set_from_icon_name(icon_name)
        self._icon.set_pixel_size(32)

        self._icon.remove_css_class("accent")
        self._icon.remove_css_class("error")
        self._icon.remove_css_class("warning")
        self._icon.remove_css_class("dim-label")
        if self._loading:
            self._icon.add_css_class("dim-label")
        elif self._missing:
            self._icon.add_css_class("warning")
        elif self._locked:
            self._icon.add_css_class("error")
        else:
            self._icon.add_css_class("accent")

    def _update_status_text(self):
        if self._loading:
            self._status_label.set_text(self._loading_message or "Working...")
        elif self._missing:
            self._status_label.set_text("Folder not found on disk")
        elif self._locked:
            self._status_label.set_text("Status: Locked")
        elif self._has_password:
            self._status_label.set_text("Status: Unlocked — password set")
        else:
            self._status_label.set_text("Status: Unlocked — no password")

    def _update_button_visibility(self):
        """Show/hide buttons based on current state."""
        if self._loading:
            self._password_button.set_visible(False)
            self._lock_button.set_visible(False)
            self._unlock_button.set_visible(False)
        elif self._missing:
            # Missing: only show Remove
            self._password_button.set_visible(False)
            self._lock_button.set_visible(False)
            self._unlock_button.set_visible(False)
        elif self._locked:
            self._password_button.set_visible(False)
            self._lock_button.set_visible(False)
            self._unlock_button.set_visible(True)
        elif self._has_password:
            self._password_button.set_visible(False)
            self._lock_button.set_visible(True)
            self._unlock_button.set_visible(False)
        else:
            self._password_button.set_visible(True)
            self._lock_button.set_visible(True)
            self._unlock_button.set_visible(False)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_remove_clicked(self, button):
        self.emit("remove-request", self._folder_path)

    def _on_password_clicked(self, button):
        self.emit("password-request", self._folder_path)

    def _on_lock_clicked(self, button):
        self.emit("lock-request", self._folder_path)

    def _on_unlock_clicked(self, button):
        self.emit("unlock-request", self._folder_path)
