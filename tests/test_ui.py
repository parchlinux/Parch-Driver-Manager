import unittest
from unittest.mock import MagicMock, patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from parch_driver_manager.ui.widgets import LogBuffer
from parch_driver_manager.ui.settings import is_rtl, get_language


class TestUIComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize GTK if not already initialized
        Gtk.init()

    def test_log_buffer_append(self):
        textview = Gtk.TextView()
        log_buffer = LogBuffer(textview, max_lines=10)
        log_buffer.append("Line 1")
        log_buffer.append("Line 2")
        
        # Flush queue manually
        log_buffer._flush()
        text = textview.get_buffer().get_text(
            textview.get_buffer().get_start_iter(),
            textview.get_buffer().get_end_iter(),
            False
        )
        self.assertIn("Line 1", text)
        self.assertIn("Line 2", text)

    def test_log_buffer_max_lines_limit(self):
        textview = Gtk.TextView()
        log_buffer = LogBuffer(textview, max_lines=5)
        for i in range(10):
            log_buffer.append(f"Line {i}")
        
        log_buffer._flush()
        line_count = textview.get_buffer().get_line_count()
        self.assertLessEqual(line_count, 6)

    def test_settings_language_and_rtl(self):
        lang = get_language()
        self.assertIsInstance(lang, str)
        rtl = is_rtl()
        self.assertIsInstance(rtl, bool)


if __name__ == "__main__":
    unittest.main()
