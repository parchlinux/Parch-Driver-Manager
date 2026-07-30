from typing import List

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from .settings import APP_ID, _
from .window import MainWindow


class ParchDriverManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        self._apply_theme()

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self._on_shortcuts)
        self.add_action(shortcuts_action)
        self.set_accels_for_action("app.shortcuts", ["<primary>question", "F1"])

        self.set_accels_for_action("win.refresh", ["<primary>r"])

    def _apply_theme(self):
        try:
            settings = Gio.Settings.new("com.parchlinux.driver-manager")
            theme = settings.get_string("theme")
        except GLib.Error:
            theme = "auto"

        style_manager = Adw.StyleManager.get_default()
        if theme == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif theme == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)

    def _on_about(self, _action, _param):
        win = self.props.active_window
        if not win:
            return
        changelog = (
            "<p>Changes in version 1.0.1:</p>"
            "<ul>"
            "<li>NVIDIA Driver Upgrade: Set nvidia-open (open-source kernel modules) as the primary NVIDIA driver.</li>"
            "<li>UI Redesign: Implemented modern GNOME HIG layout with responsive Adw.OverlaySplitView and collapsible sidebar.</li>"
            "<li>Parch Bluetooth Support: Added detection for parch-bluetooth stack alongside standard BlueZ.</li>"
            "<li>NetworkManager Detection: Fixed detection for networkmanager package and systemd service status.</li>"
            "<li>System Prober Improvements: Enhanced hybrid GPU detection (Intel, AMD, NVIDIA) and hardware cache management.</li>"
            "<li>Security and Safety: Replaced bash commands with atomic file writing and regex validation.</li>"
            "<li>Mobile Optimization: Added responsive breakpoints and touch-friendly controls.</li>"
            "</ul>"
        )
        about = Adw.AboutWindow(
            transient_for=win,
            application_name=_("Parch Driver Manager"),
            application_icon="com.parchlinux.DriverManager",
            version="1.0.1",
            developer_name="Parch GNU/Linux",
            developers=["Parch Linux Team"],
            copyright="\u00a9 2026 Parch GNU/Linux",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/parchlinux/Parch-Driver-Manager",
            issue_url="https://github.com/parchlinux/Parch-Driver-Manager/issues",
            translator_credits=_("Parch Linux Team"),
            comments=_("Hardware driver management tool for Parch GNU/Linux"),
            release_notes=changelog,
            release_notes_version="1.0.1",
        )
        about.present()

    def _on_quit(self, _action, _param):
        self.quit()

    def _on_shortcuts(self, _action, _param):
        win = self.props.active_window
        if not win:
            return
        window = Gtk.ShortcutsWindow(transient_for=win, modal=True)
        section = Gtk.ShortcutsSection(title=_("General"), section_name="general")
        group = Gtk.ShortcutsGroup(title=_("Application"))

        item1 = Gtk.ShortcutsShortcut(title=_("Refresh hardware"), accelerator="<primary>r")
        group.append(item1)

        item2 = Gtk.ShortcutsShortcut(title=_("Quit"), accelerator="<primary>q")
        group.append(item2)

        section.append(group)
        window.add_section(section)
        window.present()

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(self)
        win.present()


def main(argv: List[str]) -> int:
    app = ParchDriverManagerApp()
    return app.run(argv)
