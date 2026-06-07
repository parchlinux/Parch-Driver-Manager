import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

import sys
import threading
from typing import List, Optional, Callable

from system_prober import SystemProber, CommandError, debug_log
from backend import BackendRunner
from manager import DriverManager
from profiles import DriverProfiles, DriverProfile

APP_ID = "org.parch.DriverManager"

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

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title("Parch Driver Manager")
        self.set_default_size(1000, 650)

        self.backend = BackendRunner()
        self.manager = DriverManager(self.backend)

        self.gpu_info = SystemProber.get_gpu_info()
        self.session_type = SystemProber.get_session_type()
        self.hybrid = SystemProber.is_hybrid_graphics()
        self.secure_boot = SystemProber.has_secure_boot()
        self.hardware_devices = SystemProber.get_hardware_devices()

        self.current_profile: Optional[DriverProfile] = None
        self.profiles: List[DriverProfile] = []
        self.kernel_flavor = "default"

        self._build_ui()

    def _build_ui(self):
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.split_view = Adw.NavigationSplitView()
        self.toast_overlay.set_child(self.split_view)

        sidebar_page = Adw.NavigationPage(title="Categories")
        self.split_view.set_sidebar(sidebar_page)

        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_page.set_child(sidebar_box)

        sidebar_header = Adw.HeaderBar(show_start_title_buttons=True, show_end_title_buttons=True)
        sidebar_header.set_title_widget(Gtk.Label(label="Hardware & Drivers"))
        sidebar_box.append(sidebar_header)

        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar_list.add_css_class("navigation-sidebar")
        self.sidebar_list.connect("row-selected", self.on_sidebar_selected)
        sidebar_box.append(self.sidebar_list)

        categories = ["GPU", "Network", "Audio", "Bluetooth", "System Info", "Logs"]
        for cat in categories:
            row = Adw.ActionRow(title=cat)
            icon_name = {
                "GPU": "video-display-symbolic",
                "Network": "network-wired-symbolic",
                "Audio": "audio-speakers-symbolic",
                "Bluetooth": "bluetooth-symbolic",
                "System Info": "computer-symbolic",
                "Logs": "document-text-symbolic"
            }.get(cat, "dialog-question-symbolic")
            row.set_icon_name(icon_name)
            self.sidebar_list.append(row)

        content_page = Adw.NavigationPage(title="Content")
        self.split_view.set_content(content_page)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_page.set_child(content_box)

        self.content_header = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=True)
        self.content_title = Gtk.Label(label="Select a Category")
        self.content_header.set_title_widget(self.content_title)
        content_box.append(self.content_header)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        content_box.append(self.stack)

        self._build_gpu_page()
        self._build_network_page()
        self._build_audio_page()
        self._build_bluetooth_page()
        self._build_info_page()
        self._build_logs_page()

        GLib.idle_add(self.sidebar_list.select_row, self.sidebar_list.get_row_at_index(0))

    def _create_profile_widgets(self, profiles: List[DriverProfile]) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        
        profiles_group = Adw.PreferencesGroup(title="Recommended Driver Profiles")
        box.append(profiles_group)

        self.profile_listbox = Gtk.ListBox()
        self.profile_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.profile_listbox.add_css_class("boxed-list")
        profiles_group.add(self.profile_listbox)

        for idx, profile in enumerate(profiles):
            subtitle = f"{profile.description}"
            row = Adw.ActionRow(title=profile.name, subtitle=subtitle)
            row.set_activatable(True)
            row.connect("activated", self.on_profile_row_activated, idx)
            self.profile_listbox.append(row)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=6)
        box.append(button_box)

        self.install_button = Gtk.Button(label="Install Driver", css_classes=["suggested-action"])
        self.install_button.connect("clicked", self.on_install_clicked)
        button_box.append(self.install_button)

        self.remove_button = Gtk.Button(label="Remove Driver", css_classes=["destructive-action"])
        self.remove_button.connect("clicked", self.on_remove_clicked)
        button_box.append(self.remove_button)

        self.disable_button = Gtk.Button(label="Disable Hardware")
        self.disable_button.connect("clicked", self.on_disable_clicked)
        button_box.append(self.disable_button)

        self.enable_button = Gtk.Button(label="Enable Hardware", css_classes=["pill"])
        self.enable_button.connect("clicked", self.on_enable_clicked)
        button_box.append(self.enable_button)

        return box

    def _build_gpu_page(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)

        hw_group = Adw.PreferencesGroup(title="Detected Graphics Cards")
        main_box.append(hw_group)
        
        hw_list = Gtk.ListBox()
        hw_list.add_css_class("boxed-list")
        hw_group.add(hw_list)

        gpus = [d for d in self.hardware_devices if d['category'] == 'GPU']
        if gpus:
            for gpu in gpus:
                sub = f"Driver: {gpu['driver'] if gpu['driver'] else 'None'}"
                hw_list.append(Adw.ActionRow(title=gpu['name'], subtitle=sub))
        else:
            hw_list.append(Adw.ActionRow(title="No GPU detected", subtitle="lspci found no graphics devices"))

        self.gpu_profiles = DriverProfiles.get_gpu_profiles(self.gpu_info.get("vendor", "Unknown"), self.kernel_flavor)
        main_box.append(self._create_profile_widgets(self.gpu_profiles))
        
        self.stack.add_named(main_box, "GPU")

    def _build_network_page(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)

        hw_group = Adw.PreferencesGroup(title="Detected Network Devices")
        main_box.append(hw_group)
        hw_list = Gtk.ListBox()
        hw_list.add_css_class("boxed-list")
        hw_group.add(hw_list)

        nets = [d for d in self.hardware_devices if d['category'] == 'Network']
        if nets:
            for net in nets:
                sub = f"Driver: {net['driver'] if net['driver'] else 'None'}"
                hw_list.append(Adw.ActionRow(title=net['name'], subtitle=sub))
        else:
            hw_list.append(Adw.ActionRow(title="No Network devices detected"))

        self.net_profiles = DriverProfiles.get_network_profiles()
        main_box.append(self._create_profile_widgets(self.net_profiles))
        self.stack.add_named(main_box, "Network")

    def _build_audio_page(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)

        hw_group = Adw.PreferencesGroup(title="Detected Audio Devices")
        main_box.append(hw_group)
        hw_list = Gtk.ListBox()
        hw_list.add_css_class("boxed-list")
        hw_group.add(hw_list)

        auds = [d for d in self.hardware_devices if d['category'] == 'Audio']
        if auds:
            for aud in auds:
                sub = f"Driver: {aud['driver'] if aud['driver'] else 'None'}"
                hw_list.append(Adw.ActionRow(title=aud['name'], subtitle=sub))
        else:
            hw_list.append(Adw.ActionRow(title="No Audio devices detected"))

        self.audio_profiles = DriverProfiles.get_audio_profiles()
        main_box.append(self._create_profile_widgets(self.audio_profiles))
        self.stack.add_named(main_box, "Audio")

    def _build_bluetooth_page(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)

        hw_group = Adw.PreferencesGroup(title="Detected Bluetooth Devices")
        main_box.append(hw_group)
        hw_list = Gtk.ListBox()
        hw_list.add_css_class("boxed-list")
        hw_group.add(hw_list)

        bts = [d for d in self.hardware_devices if d['category'] == 'Bluetooth']
        if bts:
            for bt in bts:
                sub = f"Driver: {bt['driver'] if bt['driver'] else 'None'}"
                hw_list.append(Adw.ActionRow(title=bt['name'], subtitle=sub))
        else:
            hw_list.append(Adw.ActionRow(title="No Bluetooth devices detected"))

        self.bt_profiles = DriverProfiles.get_bluetooth_profiles()
        main_box.append(self._create_profile_widgets(self.bt_profiles))
        self.stack.add_named(main_box, "Bluetooth")

    def _build_info_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)

        info_group = Adw.PreferencesGroup(title="System information")
        box.append(info_group)

        info_group.add(Adw.ActionRow(title="GPU Vendor", subtitle=self.gpu_info.get("vendor", "Unknown")))
        info_group.add(Adw.ActionRow(title="Session Type", subtitle=self.session_type))
        info_group.add(Adw.ActionRow(title="Hybrid Graphics", subtitle="Enabled" if self.hybrid else "Disabled"))
        info_group.add(Adw.ActionRow(title="Secure Boot", subtitle="Enabled (may require module signing)" if self.secure_boot else "Disabled"))

        self.stack.add_named(box, "System Info")

    def _build_logs_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        
        log_label = Gtk.Label(label="Operation log", xalign=0)
        box.append(log_label)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        box.append(scrolled)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scrolled.set_child(self.log_view)

        self.log_buffer = LogBuffer(self.log_view)

        self.stack.add_named(box, "Logs")

    def on_sidebar_selected(self, listbox, row):
        if row:
            title = row.get_title()
            self.content_title.set_label(title)
            self.stack.set_visible_child_name(title)
            
            if title == "GPU": self.profiles = self.gpu_profiles
            elif title == "Network": self.profiles = self.net_profiles
            elif title == "Audio": self.profiles = self.audio_profiles
            elif title == "Bluetooth": self.profiles = self.bt_profiles
            else: self.profiles = []

    def on_profile_row_activated(self, row: Adw.ActionRow, idx: int):
        if idx < len(self.profiles):
            self.current_profile = self.profiles[idx]
            self._show_toast(f"Selected profile: {self.current_profile.name}")

    def _run_in_thread(self, target: Callable, *args, **kwargs):
        def wrapper():
            try:
                target(*args, **kwargs)
            except CommandError as e:
                msg = f"Command error: {' '.join(e.cmd)}\nExit code: {e.returncode}\n{e.stderr}"
                debug_log(msg)
                GLib.idle_add(self._show_toast, "Operation failed. See log for details.")
                self.log_buffer.append(msg)
            except Exception as e:
                msg = f"Unexpected exception: {e}"
                debug_log(msg)
                GLib.idle_add(self._show_toast, "Unexpected error. See log for details.")
                self.log_buffer.append(msg)

        threading.Thread(target=wrapper, daemon=True).start()

    def on_install_clicked(self, button: Gtk.Button):
        if not self.current_profile:
            self._show_toast("No profile selected.")
            return

        def progress(msg: str):
            self.log_buffer.append(msg)

        def task():
            self.log_buffer.append(f"Starting installation of profile: {self.current_profile.name}")
            self.manager.install_profile(self.current_profile, progress_cb=progress)
            self.log_buffer.append("Profile installation finished.")
            GLib.idle_add(self._show_toast, "Profile installed successfully.")

        self._run_in_thread(task)

    def on_remove_clicked(self, button: Gtk.Button):
        if not self.current_profile:
            self._show_toast("No profile selected.")
            return

        def progress(msg: str):
            self.log_buffer.append(msg)

        def task():
            self.log_buffer.append(f"Starting removal of profile: {self.current_profile.name}")
            self.manager.remove_profile(self.current_profile, progress_cb=progress)
            self.log_buffer.append("Profile removal finished.")
            GLib.idle_add(self._show_toast, "Profile removed successfully.")

        self._run_in_thread(task)

    def on_disable_clicked(self, button: Gtk.Button):
        if not self.current_profile:
            self._show_toast("No profile selected.")
            return
        if not self.current_profile.module:
            self._show_toast("This profile has no associated kernel module to disable.")
            return

        def progress(msg: str):
            self.log_buffer.append(msg)

        def task():
            self.log_buffer.append(f"Disabling hardware module for: {self.current_profile.name}")
            self.manager.disable_driver(self.current_profile, progress_cb=progress)
            GLib.idle_add(self._show_toast, "Hardware disabled. Reboot might be required.")

        self._run_in_thread(task)

    def on_enable_clicked(self, button: Gtk.Button):
        if not self.current_profile:
            self._show_toast("No profile selected.")
            return
        if not self.current_profile.module:
            self._show_toast("This profile has no associated kernel module to enable.")
            return

        def progress(msg: str):
            self.log_buffer.append(msg)

        def task():
            self.log_buffer.append(f"Enabling hardware module for: {self.current_profile.name}")
            self.manager.enable_driver(self.current_profile, progress_cb=progress)
            GLib.idle_add(self._show_toast, "Hardware enabled.")

        self._run_in_thread(task)

    def _show_toast(self, text: str):
        toast = Adw.Toast.new(text)
        self.toast_overlay.add_toast(toast)

class ParchDriverManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(self)
        win.present()

def main(argv: List[str]) -> int:
    app = ParchDriverManagerApp()
    return app.run(argv)
