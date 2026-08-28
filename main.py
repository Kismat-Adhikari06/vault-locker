#!/usr/bin/env python3
"""
VaultLock - A lightweight folder locking application.

This module handles the application lifecycle:
- Initializes the Adw.Application instance
- Registers the main window
- Manages application startup and shutdown
- Accepts folder paths as CLI arguments for file manager integration

Usage:
    vaultlock                    # Open normally
    vaultlock /path/to/folder    # Open with folder prompt
"""

import os
import sys
import gi

# Require GTK 4.0 and libadwaita 1.0
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk
from window import VaultLockWindow


class VaultLockApp(Adw.Application):
    """
    Main application class for VaultLock.

    Inherits from Adw.Application to get libadwaita styling
    and modern GNOME desktop integration.
    """

    def __init__(self):
        """Initialize the application with an application ID and flags."""
        super().__init__(
            application_id="com.vaultlock.app",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        # Folder path passed via CLI (for file manager integration)
        self._initial_folder = None

    def do_command_line(self, command_line):
        """
        Handle command-line arguments.

        Supports:
            vaultlock                    — open normally
            vaultlock /path/to/folder    — open with folder prompt
        """
        args = command_line.get_arguments()

        if len(args) > 1:
            # First non-program argument is the folder path
            folder_path = args[1]
            # Resolve to absolute path
            folder_path = os.path.realpath(os.path.expanduser(folder_path))
            if os.path.isdir(folder_path):
                self._initial_folder = folder_path
            else:
                print(f"[VaultLock] Warning: '{folder_path}' is not a valid directory")

        self.activate()
        return 0

    def do_activate(self):
        """
        Called when the application is activated.

        This is the main entry point where we create and show
        the main application window.
        """
        # Create the main window, passing any initial folder from CLI
        win = VaultLockWindow(application=self)

        # If a folder was passed via CLI, prompt to add it
        if self._initial_folder:
            GLib.idle_add(win._show_add_from_cli_dialog, self._initial_folder)
            self._initial_folder = None

        # Present the window to the user (makes it visible)
        win.present()


def main():
    """Entry point for the VaultLock application."""
    # Create and run the application, passing command-line arguments
    app = VaultLockApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
