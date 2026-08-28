#!/usr/bin/env python3
"""
Reusable folder list item component for VaultLock.

Each item displays:
- A folder icon
- The folder's display name (basename)
- Full path as secondary text
"""

import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GObject, Gtk


class FolderItem(Gtk.ListBoxRow):
    """
    A list row widget representing a single folder.

    Signals:
        remove-request (str): Emitted when remove is clicked.
    """

    __gsignals__ = {
        "remove-request": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, folder_path: str):
        super().__init__()

        self._folder_path = folder_path

        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        if not folder_name:
            folder_name = folder_path
        self._folder_name = folder_name

        self._build_ui()

    def _build_ui(self):
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row_box.set_margin_top(8)
        row_box.set_margin_bottom(8)
        row_box.set_margin_start(12)
        row_box.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        icon.set_pixel_size(32)
        icon.add_css_class("accent")
        row_box.append(icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        name_label = Gtk.Label(label=self._folder_name)
        name_label.set_xalign(0)
        name_label.add_css_class("heading")
        text_box.append(name_label)

        path_label = Gtk.Label(label=self._folder_path)
        path_label.set_xalign(0)
        path_label.add_css_class("caption")
        path_label.add_css_class("dim-label")
        path_label.set_ellipsize(3)
        text_box.append(path_label)

        row_box.append(text_box)

        self.set_child(row_box)

    @property
    def folder_path(self) -> str:
        return self._folder_path
