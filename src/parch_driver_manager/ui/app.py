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
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-application-prefer-dark-theme", False)

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

    def _on_about(self, _action, _param):
        win = self.props.active_window
        if not win:
            return
        about = Adw.AboutWindow(
            transient_for=win,
            application_name=_("Parch Driver Manager"),
            application_icon="com.parchlinux.DriverManager",
            version="1.0.1",
            developer_name="Parch Linux",
            copyright="\u00a9 2026 Parch Linux",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/parchlinux/Parch-Driver-Manager",
            issue_url="https://github.com/parchlinux/Parch-Driver-Manager/issues",
        )
        about.present()

    def _on_quit(self, _action, _param):
        self.quit()

    def _on_shortcuts(self, _action, _param):
        win = self.props.active_window
        if not win:
            return
        dialog = Adw.ShortcutsDialog()
        dialog.set_title(_("Keyboard Shortcuts"))
        section = Adw.ShortcutsSection()
        section.set_title(_("General"))

        item = Adw.ShortcutsItem()
        item.set_title(_("Quit"))
        item.set_accelerator("<primary>q")
        section.add(item)

        item = Adw.ShortcutsItem()
        item.set_title(_("Refresh hardware"))
        item.set_accelerator("<primary>r")
        section.add(item)

        item = Adw.ShortcutsItem()
        item.set_title(_("Keyboard shortcuts"))
        item.set_accelerator("F1")
        section.add(item)

        dialog.add(section)
        dialog.present()

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(self)
        win.present()


def main(argv: List[str]) -> int:
    app = ParchDriverManagerApp()
    return app.run(argv)
