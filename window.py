#!/usr/bin/env python3
"""
Main window module for VaultLock.

This module defines the main application window using
GTK4 and libadwaita widgets for a modern GNOME look and feel.

Features:
- Header bar with title, subtitle, and refresh button
- Scrollable folder list using Gtk.ListBox
- Dynamic empty state (shown when no folders are added)
- Folder chooser dialog using modern GTK4 FileDialog API
- Duplicate folder prevention with error feedback
- Persistent storage: folders survive app restarts
- Password management: set and verify passwords per folder
- Folder locking via gocryptfs (AES-256-GCM encryption)
- Loading states during lock/unlock operations
- Confirmation dialogs for lock and remove operations
- Startup verification: detects missing folders and stale states
- Refresh button: rechecks all folder statuses
"""

import os
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from folder_item import FolderItem
from locker import (
    is_gocryptfs_available,
    is_locked,
    lock_folder,
    unlock_folder,
    vault_exists,
)
from security import hash_password, verify_folder_password
from storage import FolderStorage


class VaultLockWindow(Adw.ApplicationWindow):
    """The main application window for VaultLock."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._storage = FolderStorage()
        self._folder_paths = []
        self._folder_widgets = {}

        # Prevent duplicate lock/unlock operations
        self._operations_in_progress = set()

        self.set_default_size(450, 550)
        self._set_window_icon()

        self._build_ui()
        self._load_saved_folders()

    def _set_window_icon(self):
        """Set the window icon using the installed vaultlock icon."""
        self.set_icon_name("vaultlock")

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header_bar = self._build_header_bar()
        toolbar_view.add_top_bar(header_bar)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._empty_state = self._build_empty_state()
        content_box.append(self._empty_state)

        self._folder_list = Gtk.ListBox()
        self._folder_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._folder_list.add_css_class("boxed-list")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self._folder_list)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_box.append(scrolled)

        button_box = self._build_add_button()
        content_box.append(button_box)

        toolbar_view.set_content(content_box)
        self.set_content(toolbar_view)

    def _build_header_bar(self) -> Adw.HeaderBar:
        header_bar = Adw.HeaderBar()

        # Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title_box.set_margin_top(2)
        title_box.set_margin_bottom(2)

        title_label = Gtk.Label(label="VaultLock")
        title_label.add_css_class("title")
        subtitle_label = Gtk.Label(label="Folder Security")
        subtitle_label.add_css_class("subtitle")

        title_box.append(title_label)
        title_box.append(subtitle_label)
        header_bar.set_title_widget(title_box)

        # Refresh button
        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_button.set_tooltip_text("Refresh all folder statuses")
        refresh_button.add_css_class("flat")
        refresh_button.connect("clicked", self._on_refresh_clicked)
        header_bar.pack_end(refresh_button)

        return header_bar

    def _build_empty_state(self) -> Gtk.Box:
        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        empty_box.set_valign(Gtk.Align.CENTER)
        empty_box.set_vexpand(True)

        empty_icon = Gtk.Image.new_from_icon_name("folder-open-symbolic")
        empty_icon.set_pixel_size(64)
        empty_icon.add_css_class("dim-label")

        empty_label = Gtk.Label(label="No folders added yet")
        empty_label.add_css_class("dim-label")

        hint_label = Gtk.Label(label='Click "+ Add Folder" to get started')
        hint_label.add_css_class("caption")
        hint_label.add_css_class("dim-label")

        empty_box.append(empty_icon)
        empty_box.append(empty_label)
        empty_box.append(hint_label)
        return empty_box

    def _build_add_button(self) -> Gtk.Box:
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        button_box.set_margin_start(12)
        button_box.set_margin_end(12)
        button_box.set_margin_top(12)
        button_box.set_margin_bottom(12)

        add_button = Gtk.Button(label="+ Add Folder")
        add_button.add_css_class("suggested-action")
        add_button.add_css_class("pill")
        add_button.set_size_request(-1, 40)
        add_button.connect("clicked", self._on_add_folder_clicked)

        button_box.append(add_button)
        return button_box

    # ==================================================================
    # Startup folder verification
    # ==================================================================

    def _load_saved_folders(self):
        """
        Load saved folders from storage and verify their state.

        On startup, each folder is checked for:
        1. Does the folder still exist on disk?
        2. Is the vault state consistent with storage?
        3. Are there any unexpected states?

        Missing folders trigger a dialog asking the user to keep or remove.
        """
        entries = self._storage.load_folder_entries()
        if not entries:
            return

        print(f"[VaultLock] Loaded {len(entries)} saved folder(s)")

        # Collect issues to show after UI is built
        missing_folders = []
        stale_entries = []

        for entry in entries:
            path = entry.get("path", "")
            if not path:
                continue

            has_password = bool(entry.get("password_hash", ""))
            stored_locked = entry.get("locked", False)

            # Check 1: Does the folder exist on disk?
            folder_exists = os.path.isdir(path)

            # Check 2: Is the vault state consistent?
            actual_locked = is_locked(path)
            vault_on_disk = vault_exists(path)

            # Reconcile lock state
            if stored_locked and not actual_locked:
                # Storage says locked but vault doesn't exist on disk
                # Could be: vault was deleted, or app closed while locked
                if vault_on_disk:
                    # Vault dir exists but gocryptfs.conf missing — corrupted
                    stale_entries.append(path)
                else:
                    # Vault completely gone — mark as unlocked
                    print(f"[VaultLock] Vault gone for {path}, marking unlocked")
                    self._storage.update_lock_status(path, locked=False)
                    stored_locked = False
            elif not stored_locked and actual_locked:
                # Storage says unlocked but vault exists — mark as locked
                print(f"[VaultLock] Vault exists for {path}, marking locked")
                self._storage.update_lock_status(path, locked=True)
                stored_locked = True

            # Handle missing folder
            if not folder_exists and not stored_locked:
                missing_folders.append(path)

            # Add to UI
            if path not in self._folder_paths:
                self._add_folder(
                    path,
                    save=False,
                    has_password=has_password,
                    locked=stored_locked,
                    missing=(not folder_exists and not stored_locked),
                )

        # Show missing folder dialogs after UI is fully loaded
        if missing_folders:
            GLib.idle_add(self._show_missing_folders_dialog, missing_folders)

        if stale_entries:
            GLib.idle_add(self._show_stale_entries_dialog, stale_entries)

    def _show_missing_folders_dialog(self, paths):
        """Show a dialog listing missing folders and asking what to do."""
        if not paths:
            return False

        folder_names = []
        for p in paths:
            name = os.path.basename(p.rstrip(os.sep))
            folder_names.append(name if name else p)

        name_list = "\n".join(f"  • {n}" for n in folder_names)

        dialog = Adw.AlertDialog(
            heading="Folders Not Found",
            body=f"The following folders no longer exist:\n{name_list}\n\n"
                 "Would you like to remove them from VaultLock?",
        )
        dialog.add_response("keep", "Keep")
        dialog.add_response("remove", "Remove All")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("keep", Adw.ResponseAppearance.DEFAULT)
        dialog.set_default_response("keep")
        dialog.set_close_response("keep")

        def on_response(dlg, response):
            if response == "remove":
                for path in paths:
                    self._remove_folder(path)

        dialog.connect("response", on_response)
        dialog.present(self)
        return False  # Don't call idle_add again

    def _show_stale_entries_dialog(self, paths):
        """Show a dialog for folders with corrupted vault state."""
        if not paths:
            return False

        folder_names = []
        for p in paths:
            name = os.path.basename(p.rstrip(os.sep))
            folder_names.append(name if name else p)

        name_list = "\n".join(f"  • {n}" for n in folder_names)

        dialog = Adw.AlertDialog(
            heading="Corrupted Vault Detected",
            body=f"The following vaults appear corrupted:\n{name_list}\n\n"
                 "The vault directory exists but is not properly initialized. "
                 "The affected folders have been marked as unlocked.",
        )
        dialog.add_response("ok", "OK")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.DEFAULT)
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.present(self)
        return False

    # ==================================================================
    # Refresh
    # ==================================================================

    def _on_refresh_clicked(self, button):
        """Recheck all folder statuses and update the UI."""
        print("[VaultLock] Refreshing folder statuses...")

        # Collect any missing folders found during refresh
        missing_folders = []

        for path in list(self._folder_paths):
            widget = self._folder_widgets.get(path)
            if not widget:
                continue

            # Check if folder exists on disk
            folder_exists = os.path.isdir(path)

            # Check vault state
            actual_locked = is_locked(path)
            vault_on_disk = vault_exists(path)

            # Reconcile
            if actual_locked and not folder_exists:
                # Folder was locked (moved to vault) — that's expected
                widget.set_locked()
                self._storage.update_lock_status(path, locked=True)
            elif not folder_exists and not actual_locked:
                # Folder doesn't exist and not locked — it's gone
                widget.set_missing()
                missing_folders.append(path)
            elif folder_exists and not actual_locked:
                # Folder exists and unlocked
                widget.set_unlocked()
                # Ensure has_password state is correct
                entries = self._storage.load_folder_entries()
                for entry in entries:
                    if entry.get("path") == path:
                        if entry.get("password_hash"):
                            widget.set_password_set()
                        break
            elif not vault_on_disk and actual_locked:
                # Vault gone but storage says locked — stale
                widget.set_unlocked()
                self._storage.update_lock_status(path, locked=False)
            else:
                # Everything consistent
                if actual_locked:
                    widget.set_locked()
                else:
                    widget.set_unlocked()

        if missing_folders:
            self._show_missing_folders_dialog(missing_folders)
        else:
            # Show brief "all good" indicator
            self._show_toast("All folder statuses updated")

    def _show_toast(self, message):
        """Show a toast notification at the bottom of the window."""
        toast = Adw.Toast(title=message)
        toast.set_timeout(2)
        if hasattr(self, '_toast_overlay'):
            self._toast_overlay.add_toast(toast)
        else:
            print(f"[VaultLock] {message}")

    # ==================================================================
    # CLI / File Manager Integration
    # ==================================================================

    def _show_add_from_cli_dialog(self, folder_path):
        """
        Show a confirmation dialog when a folder is passed via CLI.

        This is triggered by file manager integration (right-click →
        "Lock with VaultLock") or by running:
            vaultlock /path/to/folder

        Args:
            folder_path: The absolute path of the folder to add.
        """
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        # Check if already added
        if self._is_folder_added(folder_path):
            self._show_duplicate_error(folder_path)
            return False

        dialog = Adw.AlertDialog(
            heading=f"Add \"{folder_name}\"?",
            body=f"Do you want to add this folder to VaultLock?\n\n"
                 f"Path: {folder_path}",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add Folder")
        dialog.add_response("add_lock", "Add and Lock")
        dialog.set_response_appearance("add_lock", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("add", Adw.ResponseAppearance.DEFAULT)
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DEFAULT)
        dialog.set_default_response("add_lock")
        dialog.set_close_response("cancel")

        def on_response(dlg, response):
            if response == "add":
                # Just add the folder
                self._add_folder(folder_path, save=True)
            elif response == "add_lock":
                # Add the folder, then immediately start lock flow
                self._add_folder(folder_path, save=True)
                # Trigger the lock workflow
                GLib.idle_add(self._on_folder_lock_request, None, folder_path)

        dialog.connect("response", on_response)
        dialog.present(self)
        return False  # Don't call idle_add again

    # ==================================================================
    # Folder selection
    # ==================================================================

    def _on_add_folder_clicked(self, button):
        dialog = Gtk.FileDialog()
        dialog.set_title("Select a Folder to Lock")
        dialog.set_modal(True)
        dialog.select_folder(parent=self, callback=self._on_folder_selected)

    def _on_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return

        if folder is None:
            return

        folder_path = folder.get_path()
        if folder_path is None:
            return

        folder_path = os.path.realpath(folder_path)

        if self._is_folder_added(folder_path):
            self._show_duplicate_error(folder_path)
            return

        self._add_folder(folder_path, save=True)

    # ==================================================================
    # Folder list management
    # ==================================================================

    def _add_folder(self, folder_path, save=True, has_password=False,
                    locked=False, missing=False):
        self._folder_paths.append(folder_path)

        item = FolderItem(
            folder_path,
            has_password=has_password,
            locked=locked,
            missing=missing,
        )

        # Connect all signals
        item.connect("remove-request", self._on_folder_remove_request)
        item.connect("password-request", self._on_folder_password_request)
        item.connect("lock-request", self._on_folder_lock_request)
        item.connect("unlock-request", self._on_folder_unlock_request)
        item.connect("change-password-request", self._on_folder_change_password_request)

        self._folder_list.append(item)
        self._folder_widgets[folder_path] = item
        self._update_empty_state()

        if save:
            self._storage.save_folders(self._folder_paths)

        print(f"[VaultLock] Added folder: {folder_path}")

    def _remove_folder(self, folder_path):
        self._folder_paths.remove(folder_path)
        self._folder_widgets.pop(folder_path, None)

        child = self._folder_list.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            if isinstance(child, FolderItem) and child.folder_path == folder_path:
                self._folder_list.remove(child)
                break
            child = next_child

        self._update_empty_state()
        self._storage.save_folders(self._folder_paths)
        print(f"[VaultLock] Removed folder: {folder_path}")

    def _is_folder_added(self, folder_path):
        return folder_path in self._folder_paths

    def _update_empty_state(self):
        has_folders = len(self._folder_paths) > 0
        self._empty_state.set_visible(not has_folders)

    def _on_folder_remove_request(self, item, folder_path):
        """Handle remove request — ask for password if one is set."""
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        # Check if this folder has a password set
        entries = self._storage.load_folder_entries()
        has_password = False
        is_folder_locked = False
        for entry in entries:
            if entry.get("path") == folder_path:
                has_password = bool(entry.get("password_hash"))
                is_folder_locked = entry.get("locked", False)
                break

        if has_password:
            self._show_remove_password_dialog(folder_path, is_folder_locked)
        else:
            # No password set — ask for simple confirmation
            self._show_remove_confirm_dialog(folder_path)

    def _show_remove_password_dialog(self, folder_path, is_locked):
        """Show a password dialog when removing a password-protected folder."""
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        dialog = Adw.AlertDialog(
            heading=f"Remove {folder_name}?",
            body="Enter the folder password to confirm removal.",
        )

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content_box.set_margin_top(8)

        pw_label = Gtk.Label(label="Password:")
        pw_label.set_xalign(0)
        content_box.append(pw_label)

        password_entry = Gtk.PasswordEntry()
        password_entry.set_show_peek_icon(True)
        password_entry.set_tooltip_text("Enter folder password")
        content_box.append(password_entry)

        dialog.set_extra_child(content_box)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DEFAULT)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(dlg, response):
            if response == "remove":
                password = password_entry.get_text()
                if not password:
                    self._show_error("Empty Password", "Password cannot be empty.")
                    return

                # Verify password against stored hash
                if not verify_folder_password(folder_path, password):
                    self._show_error("Wrong Password", "The password you entered is incorrect.")
                    return

                # Password correct — proceed with removal
                self._do_remove_folder(folder_path, is_locked)

        dialog.connect("response", on_response)
        dialog.present(self)

    def _show_remove_confirm_dialog(self, folder_path):
        """Show a confirmation dialog for removing a folder with no password."""
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        dialog = Adw.AlertDialog(
            heading=f"Remove {folder_name}?",
            body="Are you sure you want to remove this folder from VaultLock?",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DEFAULT)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(dlg, response):
            if response == "remove":
                self._do_remove_folder(folder_path, is_locked=False)

        dialog.connect("response", on_response)
        dialog.present(self)

    def _do_remove_folder(self, folder_path, is_locked):
        """Actually remove the folder — clean up vault if locked, then remove from list."""
        if is_locked:
            import shutil
            from locker import _vault_path
            vault = _vault_path(folder_path)
            if os.path.exists(vault):
                shutil.rmtree(vault, ignore_errors=True)
                print(f"[VaultLock] Deleted vault: {vault}")
        self._remove_folder(folder_path)

    def _show_duplicate_error(self, folder_path):
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        dialog = Adw.AlertDialog(
            heading="Folder Already Added",
            body=f'"{folder_name}" is already in your locked folders list.',
        )
        dialog.add_response("ok", "OK")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.present(self)

    # ==================================================================
    # Password management
    # ==================================================================

    def _on_folder_password_request(self, item, folder_path):
        """Show the Set Password dialog."""
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        dialog = Adw.AlertDialog(
            heading=f"Set Password for {folder_name}",
            body="Choose a password to protect this folder.",
        )

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content_box.set_margin_top(8)

        password_entry = Gtk.PasswordEntry()
        password_entry.set_show_peek_icon(True)
        password_entry.set_tooltip_text("Enter password")

        password_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        password_label = Gtk.Label(label="Password:")
        password_label.set_xalign(0)
        password_row.append(password_label)
        password_row.append(password_entry)
        content_box.append(password_row)

        confirm_entry = Gtk.PasswordEntry()
        confirm_entry.set_show_peek_icon(True)
        confirm_entry.set_tooltip_text("Confirm password")

        confirm_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        confirm_label = Gtk.Label(label="Confirm Password:")
        confirm_label.set_xalign(0)
        confirm_row.append(confirm_label)
        confirm_row.append(confirm_entry)
        content_box.append(confirm_row)

        dialog.set_extra_child(content_box)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DEFAULT)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def on_response(dlg, response):
            if response == "save":
                self._handle_password_save(
                    folder_path,
                    password_entry.get_text(),
                    confirm_entry.get_text(),
                )

        dialog.connect("response", on_response)
        dialog.present(self)

    def _handle_password_save(self, folder_path, password, confirm):
        if not password:
            self._show_error("Empty Password", "Password cannot be empty.")
            return

        if password != confirm:
            self._show_error("Passwords Don't Match", "The two passwords do not match. Please try again.")
            return

        hashed = hash_password(password)
        self._storage.update_folder_password(folder_path, hashed, locked=False)

        widget = self._folder_widgets.get(folder_path)
        if widget:
            widget.set_password_set()

        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path
        print(f"[VaultLock] Password set for: {folder_name}")

    def _on_folder_change_password_request(self, item, folder_path):
        """Show the Change Password dialog."""
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        dialog = Adw.AlertDialog(
            heading=f"Change Password for {folder_name}",
            body="Enter your current password and choose a new one.",
        )

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content_box.set_margin_top(8)

        # Current password
        current_entry = Gtk.PasswordEntry()
        current_entry.set_show_peek_icon(True)
        current_entry.set_tooltip_text("Current password")

        current_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        current_label = Gtk.Label(label="Current Password:")
        current_label.set_xalign(0)
        current_row.append(current_label)
        current_row.append(current_entry)
        content_box.append(current_row)

        # New password
        new_entry = Gtk.PasswordEntry()
        new_entry.set_show_peek_icon(True)
        new_entry.set_tooltip_text("New password")

        new_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        new_label = Gtk.Label(label="New Password:")
        new_label.set_xalign(0)
        new_row.append(new_label)
        new_row.append(new_entry)
        content_box.append(new_row)

        # Confirm new password
        confirm_entry = Gtk.PasswordEntry()
        confirm_entry.set_show_peek_icon(True)
        confirm_entry.set_tooltip_text("Confirm new password")

        confirm_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        confirm_label = Gtk.Label(label="Confirm New Password:")
        confirm_label.set_xalign(0)
        confirm_row.append(confirm_label)
        confirm_row.append(confirm_entry)
        content_box.append(confirm_row)

        dialog.set_extra_child(content_box)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Change Password")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DEFAULT)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def on_response(dlg, response):
            if response == "save":
                self._handle_password_change(
                    folder_path,
                    current_entry.get_text(),
                    new_entry.get_text(),
                    confirm_entry.get_text(),
                )

        dialog.connect("response", on_response)
        dialog.present(self)

    def _handle_password_change(self, folder_path, current_pw, new_pw, confirm_pw):
        """Process a password change request."""
        if not current_pw:
            self._show_error("Empty Password", "Current password cannot be empty.")
            return

        if not new_pw:
            self._show_error("Empty Password", "New password cannot be empty.")
            return

        if new_pw != confirm_pw:
            self._show_error("Passwords Don't Match", "The new passwords do not match.")
            return

        if current_pw == new_pw:
            self._show_error("Same Password", "New password must be different from current password.")
            return

        widget = self._folder_widgets.get(folder_path)
        if widget:
            widget.set_loading(True, "Changing password...")

        self._operations_in_progress.add(folder_path)

        def do_change():
            try:
                from locker import change_password
                change_password(folder_path, current_pw, new_pw)
                # Update stored hash
                from security import hash_password
                hashed = hash_password(new_pw)
                self._storage.update_folder_password(folder_path, hashed, locked=True)
                GLib.idle_add(self._on_password_change_complete, folder_path, True, None)
            except Exception as e:
                GLib.idle_add(self._on_password_change_complete, folder_path, False, str(e))

        thread = threading.Thread(target=do_change, daemon=True)
        thread.start()

    def _on_password_change_complete(self, folder_path, success, error):
        """Called on main thread after password change completes."""
        self._operations_in_progress.discard(folder_path)
        widget = self._folder_widgets.get(folder_path)
        if widget:
            widget.set_loading(False)

        if error:
            self._show_error("Password Change Failed", str(error))
        else:
            folder_name = os.path.basename(folder_path.rstrip(os.sep))
            if not folder_name:
                folder_name = folder_path
            print(f"[VaultLock] Password changed for: {folder_name}")

        return False

    # ==================================================================
    # Lock / Unlock
    # ==================================================================

    def _on_folder_lock_request(self, item, folder_path):
        """
        Handle the lock-request signal.

        Workflow:
        1. Check folder exists
        2. Check password is set
        3. Check gocryptfs is installed
        4. Check not already locked
        5. Check not already in progress
        6. Ask for confirmation
        7. Ask for password
        8. Lock the folder
        """
        # Prevent duplicate operations
        if folder_path in self._operations_in_progress:
            self._show_error(
                "Operation In Progress",
                "An operation is already in progress for this folder. Please wait.",
            )
            return

        # Check folder exists
        if not os.path.isdir(folder_path):
            self._show_error(
                "Folder Not Found",
                f'The folder "{folder_path}" does not exist or has been moved.',
            )
            return

        # Check already locked
        if is_locked(folder_path):
            self._show_error(
                "Already Locked",
                "This folder is already locked.",
            )
            return

        # Check password is set
        entries = self._storage.load_folder_entries()
        has_password = False
        for e in entries:
            if e.get("path") == folder_path and e.get("password_hash"):
                has_password = True
                break

        if not has_password:
            self._show_error(
                "No Password Set",
                "Please set a password first before locking this folder.",
            )
            return

        # Check gocryptfs availability
        if not is_gocryptfs_available():
            self._show_error(
                "Encryption Backend Missing",
                "gocryptfs is required for folder locking.\n\n"
                "  Ubuntu/Debian: sudo apt install gocryptfs\n"
                "  Fedora:        sudo dnf install gocryptfs\n"
                "  Arch:          sudo pacman -S gocryptfs",
            )
            return

        # Ask for confirmation before locking
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        dialog = Adw.AlertDialog(
            heading=f"Lock {folder_name}?",
            body="Are you sure you want to lock this folder?\n\n"
                 "After locking, files will only be accessible after unlocking.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("lock", "Lock")
        dialog.set_response_appearance("lock", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DEFAULT)
        dialog.set_default_response("lock")
        dialog.set_close_response("cancel")

        def on_confirm(dlg, response):
            if response == "lock":
                self._show_password_confirm_dialog(folder_path, "lock")

        dialog.connect("response", on_confirm)
        dialog.present(self)

    def _on_folder_unlock_request(self, item, folder_path):
        """Handle the unlock-request signal."""
        # Prevent duplicate operations
        if folder_path in self._operations_in_progress:
            self._show_error(
                "Operation In Progress",
                "An operation is already in progress for this folder. Please wait.",
            )
            return

        # Check gocryptfs availability
        if not is_gocryptfs_available():
            self._show_error(
                "Encryption Backend Missing",
                "gocryptfs is required to unlock folders.\n\n"
                "  Ubuntu/Debian: sudo apt install gocryptfs\n"
                "  Fedora:        sudo dnf install gocryptfs\n"
                "  Arch:          sudo pacman -S gocryptfs",
            )
            return

        # Check not already unlocked
        if not is_locked(folder_path):
            self._show_error(
                "Already Unlocked",
                "This folder is already unlocked.",
            )
            return

        self._show_password_confirm_dialog(folder_path, "unlock")

    def _show_password_confirm_dialog(self, folder_path, action):
        """
        Show a dialog asking the user to enter their password.

        Args:
            folder_path: The folder to lock or unlock.
            action: Either "lock" or "unlock".
        """
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        if action == "lock":
            heading = f"Enter Password to Lock {folder_name}"
            body = "Enter your password to encrypt this folder."
            button_label = "Lock"
        else:
            heading = f"Enter Password to Unlock {folder_name}"
            body = "Enter your password to decrypt this folder."
            button_label = "Unlock"

        dialog = Adw.AlertDialog(heading=heading, body=body)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content_box.set_margin_top(8)

        password_entry = Gtk.PasswordEntry()
        password_entry.set_show_peek_icon(True)
        password_entry.set_tooltip_text("Enter password")

        pw_label = Gtk.Label(label="Password:")
        pw_label.set_xalign(0)
        content_box.append(pw_label)
        content_box.append(password_entry)

        dialog.set_extra_child(content_box)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("confirm", button_label)
        dialog.set_response_appearance("confirm", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DEFAULT)
        dialog.set_default_response("confirm")
        dialog.set_close_response("cancel")

        def on_response(dlg, response):
            if response == "confirm":
                password = password_entry.get_text()
                if not password:
                    self._show_error("Empty Password", "Password cannot be empty.")
                    return

                if action == "lock":
                    self._perform_lock(folder_path, password)
                else:
                    self._perform_unlock(folder_path, password)

        dialog.connect("response", on_response)
        dialog.present(self)

    def _perform_lock(self, folder_path, password):
        """Verify password and lock the folder (runs encryption in a thread)."""
        # Verify password against stored hash
        if not verify_folder_password(folder_path, password):
            self._show_error("Wrong Password", "The password you entered is incorrect.")
            return

        widget = self._folder_widgets.get(folder_path)
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        # Show loading state
        if widget:
            widget.set_loading(True, "Locking...")

        # Mark operation in progress
        self._operations_in_progress.add(folder_path)

        def do_lock():
            try:
                lock_folder(folder_path, password)
                # Update storage: mark as locked
                self._storage.update_lock_status(folder_path, locked=True)
                # Update UI on the main thread
                GLib.idle_add(self._on_lock_complete, folder_path, True, None)
            except Exception as e:
                GLib.idle_add(self._on_lock_complete, folder_path, False, str(e))

        print(f"[VaultLock] Locking folder: {folder_name}...")
        thread = threading.Thread(target=do_lock, daemon=True)
        thread.start()

    def _perform_unlock(self, folder_path, password):
        """Verify password and unlock the folder (runs decryption in a thread)."""
        if not verify_folder_password(folder_path, password):
            self._show_error("Wrong Password", "The password you entered is incorrect.")
            return

        widget = self._folder_widgets.get(folder_path)
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        # Show loading state
        if widget:
            widget.set_loading(True, "Unlocking...")

        # Mark operation in progress
        self._operations_in_progress.add(folder_path)

        def do_unlock():
            try:
                unlock_folder(folder_path, password)
                self._storage.update_lock_status(folder_path, locked=False)
                GLib.idle_add(self._on_lock_complete, folder_path, False, None)
            except Exception as e:
                GLib.idle_add(self._on_lock_complete, folder_path, None, str(e))

        print(f"[VaultLock] Unlocking folder: {folder_name}...")
        thread = threading.Thread(target=do_unlock, daemon=True)
        thread.start()

    def _on_lock_complete(self, folder_path, locked, error):
        """
        Called on the main thread after lock/unlock completes.

        Args:
            folder_path: The folder that was processed.
            locked: True if locked, False if unlocked, None if error.
            error: Error message string, or None on success.
        """
        # Remove from operations in progress
        self._operations_in_progress.discard(folder_path)

        widget = self._folder_widgets.get(folder_path)
        if not widget:
            return False

        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path

        if error:
            widget.set_loading(False)
            self._show_error("Operation Failed", f"Could not complete operation:\n{error}")
            print(f"[VaultLock] Error: {error}")
        elif locked is True:
            widget.set_locked()
            print(f"[VaultLock] Folder locked: {folder_name}")
        elif locked is False:
            widget.set_unlocked()
            print(f"[VaultLock] Folder unlocked: {folder_name}")

        return False  # Don't call idle_add again

    # ==================================================================
    # Dialogs
    # ==================================================================

    def _show_error(self, heading="Error", message=""):
        """Show an error dialog with a heading and message."""
        dialog = Adw.AlertDialog(heading=heading, body=message)
        dialog.add_response("ok", "OK")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.present(self)
