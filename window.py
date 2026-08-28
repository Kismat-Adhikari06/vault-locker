#!/usr/bin/env python3
"""
Main window module for VaultLock.

This module defines the main application window using
GTK4 and libadwaita widgets for a modern GNOME look and feel.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk


class VaultLockWindow(Adw.ApplicationWindow):
    """The main application window for VaultLock."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_default_size(450, 550)

        self._build_ui()

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header_bar = self._build_header_bar()
        toolbar_view.add_top_bar(header_bar)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

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
        content_box.append(empty_box)

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

    def _on_add_folder_clicked(self, button):
        print("[VaultLock] Add Folder button clicked - functionality coming soon!")
