import queue
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib


class LogBuffer:
    def __init__(self, textview: Gtk.TextView, max_lines: int = 1000):
        self.textview = textview
        self.buffer = textview.get_buffer()
        self.max_lines = max_lines
        self._queue = queue.Queue()
        self._scheduled = False

    def append(self, text: str):
        self._queue.put(text)
        if not self._scheduled:
            self._scheduled = True
            GLib.idle_add(self._flush)

    def _flush(self):
        while not self._queue.empty():
            try:
                text = self._queue.get_nowait()
                end_iter = self.buffer.get_end_iter()
                self.buffer.insert(end_iter, text + "\n")
            except queue.Empty:
                break

        line_count = self.buffer.get_line_count()
        if line_count > self.max_lines:
            start_iter = self.buffer.get_start_iter()
            res = self.buffer.get_iter_at_line(line_count - self.max_lines)
            cut_iter = res[1] if isinstance(res, tuple) or hasattr(res, "__getitem__") else res
            self.buffer.delete(start_iter, cut_iter)

        mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), False)
        self.textview.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
        self._scheduled = False
        return False
