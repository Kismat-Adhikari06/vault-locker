#!/usr/bin/env python3
"""
VaultLock - A lightweight folder locking application.

This module handles the application lifecycle:
- Initializes the Adw.Application instance
- Registers the main window
- Manages application startup and shutdown
"""

import sys
import gi

# Require GTK 4.0 and libadwaita 1.0
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1.0")

from gi.repository import Adw, Gtk
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
            flags=Adw.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self):
        """
        Called when the application is activated.

        This is the main entry point where we create and show
        the main application window.
        """
        # Create the main window, passing the application reference
        win = VaultLockWindow(application=self)

        # Present the window to the user (makes it visible)
        win.present()


def main():
    """Entry point for the VaultLock application."""
    # Create and run the application, passing command-line arguments
    app = VaultLockApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
