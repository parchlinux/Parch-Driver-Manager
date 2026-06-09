import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib


class LogBuffer:
    def __init__(self, textview: Gtk.TextView):
        self.textview = textview
        self.buffer = textview.get_buffer()

    def append(self, text: str):
        def _append():
            end_iter = self.buffer.get_end_iter()
            self.buffer.insert(end_iter, text + "\n")
            mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), False)
            self.textview.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
        GLib.idle_add(_append)
