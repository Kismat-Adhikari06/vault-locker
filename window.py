#!/usr/bin/env python3
"""
Main window module for VaultLock.

Features:
- Header bar with title and subtitle
- Scrollable folder list using Gtk.ListBox
- Dynamic empty state (shown when no folders are added)
- Folder chooser dialog using modern GTK4 FileDialog API
- Duplicate folder prevention with error feedback
"""

import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk


class VaultLockWindow(Adw.ApplicationWindow):
    """The main application window for VaultLock."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._folder_paths = []

        self.set_default_size(450, 550)

        self._build_ui()

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

        self._add_folder(folder_path)

    def _add_folder(self, folder_path):
        self._folder_paths.append(folder_path)

        # Create a simple row
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row_box.set_margin_top(8)
        row_box.set_margin_bottom(8)
        row_box.set_margin_start(12)
        row_box.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        icon.set_pixel_size(32)
        icon.add_css_class("accent")
        row_box.append(icon)

        name = os.path.basename(folder_path.rstrip(os.sep))
        label = Gtk.Label(label=name)
        label.set_xalign(0)
        label.set_hexpand(True)
        row_box.append(label)

        row = Gtk.ListBoxRow()
        row.set_child(row_box)
        self._folder_list.append(row)

        self._update_empty_state()
        print(f"[VaultLock] Added folder: {folder_path}")

    def _is_folder_added(self, folder_path):
        return folder_path in self._folder_paths

    def _update_empty_state(self):
        has_folders = len(self._folder_paths) > 0
        self._empty_state.set_visible(not has_folders)

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
