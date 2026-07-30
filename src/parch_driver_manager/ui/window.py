import logging
import os
import threading
from typing import List, Optional, Callable, Dict, Tuple, Any

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

logger = logging.getLogger(__name__)

from ..system_prober import SystemProber, CommandError
from ..backend import BackendRunner
from ..manager import DriverManager
from ..profiles import DriverProfiles, DriverProfile

from .settings import _, is_rtl
from .widgets import LogBuffer


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        try:
            self.settings = Gio.Settings.new("com.parchlinux.driver-manager")
        except GLib.Error:
            self.settings = None
        super().__init__(application=app)
        self.set_title(_("Parch Driver Manager"))

        if self.settings:
            saved_w = self.settings.get_int("window-width")
            saved_h = self.settings.get_int("window-height")
            self.set_default_size(max(saved_w, 360), max(saved_h, 500))
            if self.settings.get_boolean("window-maximized"):
                self.maximize()
        else:
            self.set_default_size(950, 680)

        backend_env = os.environ.get("PARCH_DM_BACKEND", "pkexec")
        use_pkexec = backend_env not in ("none", "sudo", "doas")
        self.backend = BackendRunner(use_pkexec=use_pkexec)
        self.manager = DriverManager(self.backend)

        self._probe_hardware()

        self.profile_rows: Dict[str, List[Tuple[Adw.ActionRow, DriverProfile, Gtk.Box]]] = {}
        self.current_category: str = "GPU"
        self.current_operation: Optional[threading.Thread] = None
        self._progress_timeout_id: Optional[int] = None

        if is_rtl():
            self.set_direction(Gtk.TextDirection.RTL)

        self._build_ui()
        self._connect_window_state()

    def _probe_hardware(self):
        self.hardware_devices = SystemProber.get_hardware_devices()
        self.gpu_info = SystemProber.get_gpu_info()
        self.hybrid = SystemProber.is_hybrid_graphics()
        self.secure_boot = SystemProber.has_secure_boot()
        self.kernel_info = SystemProber.get_kernel_info()
        self.system_info = SystemProber.get_system_info()
        self.session_type = SystemProber.get_session_type()
        self.kernel_flavor = self.kernel_info.get('flavor', 'default')

    def _connect_window_state(self):
        if not self.settings:
            return

        def on_close(widget, *args):
            if not self.is_maximized():
                self.settings.set_int("window-width", self.get_width())
                self.settings.set_int("window-height", self.get_height())
            self.settings.set_boolean("window-maximized", self.is_maximized())
            return False
        self.connect("close-request", on_close)

    def _build_ui(self):
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # Overlay Split View (standard GNOME collapsible sidebar)
        self.split_view = Adw.OverlaySplitView()
        self.split_view.set_min_sidebar_width(240)
        self.split_view.set_max_sidebar_width(300)
        self.split_view.set_sidebar_position(Gtk.PackType.START)
        self.split_view.set_show_sidebar(True)
        self.toast_overlay.set_child(self.split_view)

        # Responsive Mobile Breakpoint
        bp_mobile = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 720px"))
        bp_mobile.add_setter(self.split_view, "collapsed", True)
        self.add_breakpoint(bp_mobile)

        # Sidebar Panel
        sidebar_toolbar = Adw.ToolbarView()
        self.split_view.set_sidebar(sidebar_toolbar)

        sidebar_header = Adw.HeaderBar()
        sidebar_header.add_css_class("flat")
        sidebar_title = Adw.WindowTitle(title=_("Parch Drivers"), subtitle=_("Categories"))
        sidebar_header.set_title_widget(sidebar_title)
        sidebar_toolbar.add_top_bar(sidebar_header)

        refresh_button = Gtk.Button()
        refresh_button.set_icon_name("view-refresh-symbolic")
        refresh_button.set_tooltip_text(_("Refresh hardware detection"))
        refresh_button.add_css_class("flat")
        refresh_button.connect("clicked", self.on_refresh_hardware)
        sidebar_header.pack_start(refresh_button)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_toolbar.set_content(sidebar_scroll)

        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar_box.set_margin_top(8)
        sidebar_box.set_margin_bottom(8)
        sidebar_box.set_margin_start(8)
        sidebar_box.set_margin_end(8)
        sidebar_scroll.set_child(sidebar_box)

        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar_list.add_css_class("navigation-sidebar")
        self.sidebar_list.add_css_class("boxed-list")
        self.sidebar_list.set_vexpand(True)
        self.sidebar_list.connect("row-selected", self.on_sidebar_selected)
        sidebar_box.append(self.sidebar_list)

        self._populate_sidebar()

        # Content Panel
        content_toolbar = Adw.ToolbarView()
        self.split_view.set_content(content_toolbar)

        self.content_header = Adw.HeaderBar()
        self.content_header.add_css_class("flat")
        self.content_window_title = Adw.WindowTitle(title=_("Select a Category"), subtitle=_("Parch Driver Manager"))
        self.content_header.set_title_widget(self.content_window_title)
        content_toolbar.add_top_bar(self.content_header)

        toggle_sidebar_btn = Gtk.Button()
        toggle_sidebar_btn.set_icon_name("sidebar-show-symbolic")
        toggle_sidebar_btn.set_tooltip_text(_("Toggle Sidebar"))
        toggle_sidebar_btn.add_css_class("flat")
        toggle_sidebar_btn.connect("clicked", self.on_toggle_sidebar)
        self.content_header.pack_start(toggle_sidebar_btn)

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text(_("Menu"))
        self.content_header.pack_end(menu_button)

        menu = Gio.Menu()
        app_section = Gio.Menu()
        app_section.append(_("Keyboard Shortcuts"), "app.shortcuts")
        menu.append_section(None, app_section)

        help_section = Gio.Menu()
        help_section.append(_("About"), "app.about")
        menu.append_section(None, help_section)

        quit_section = Gio.Menu()
        quit_section.append(_("Quit"), "app.quit")
        menu.append_section(None, quit_section)

        menu_button.set_menu_model(menu)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_visible(False)
        content_toolbar.add_top_bar(self.progress_bar)

        stack_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        stack_box.set_vexpand(True)
        content_toolbar.set_content(stack_box)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(250)
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)
        stack_box.append(self.stack)

        self._rebuild_all_pages()

        GLib.idle_add(self.sidebar_list.select_row, self.sidebar_list.get_row_at_index(0))

        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", lambda *_: self.on_refresh_hardware(None))
        self.add_action(refresh_action)

        self._load_css()

    def on_toggle_sidebar(self, _button=None):
        self.split_view.set_show_sidebar(not self.split_view.get_show_sidebar())

    def _populate_sidebar(self):
        while True:
            row = self.sidebar_list.get_row_at_index(0)
            if not row:
                break
            self.sidebar_list.remove(row)

        gpu_sub = self.gpu_info.get("vendor", "Graphics")
        if self.gpu_info.get("model"):
            gpu_sub = f"{gpu_sub} ({self.gpu_info.get('model')})"

        bt_active = SystemProber.is_bluetooth_service_running() or SystemProber.is_bluetooth_kernel_module_loaded() or self.manager.is_package_installed("parch-bluetooth") or self.manager.is_package_installed("bluez")
        bt_sub = _("Active") if bt_active else _("Disabled")

        categories = [
            (_("GPU"), "computer-symbolic", gpu_sub, _("Graphics Drivers")),
            (_("Network"), "network-wireless-symbolic", f"{len([d for d in self.hardware_devices if d['category'] == 'Network'])} device(s)", _("Network Interfaces")),
            (_("Audio"), "audio-card-symbolic", "PipeWire / ALSA", _("Audio Stack")),
            (_("Bluetooth"), "preferences-system-bluetooth-symbolic", bt_sub, _("Bluetooth Services")),
            (_("System Info"), "preferences-system-symbolic", self.system_info.get("os", "Parch GNU/Linux"), _("Hardware and OS Details")),
            (_("Logs"), "text-x-generic-symbolic", _("Operation logs"), _("Activity and Event Logs"))
        ]

        for cat, icon, sub, subtitle_desc in categories:
            row = Adw.ActionRow(title=cat, subtitle=sub)
            row.set_icon_name(icon)
            
            # Active indicator badge
            if cat in (_("GPU"), _("Network"), _("Audio"), _("Bluetooth")):
                active_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
                active_icon.add_css_class("success-icon")
                row.add_suffix(active_icon)
                
            self.sidebar_list.append(row)

    def _rebuild_all_pages(self):
        child = self.stack.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.stack.remove(child)
            child = next_child

        self.profile_rows.clear()
        self._build_gpu_page()
        self._build_network_page()
        self._build_audio_page()
        self._build_bluetooth_page()
        self._build_info_page()
        self._build_logs_page()

    def _is_profile_installed(self, profile: DriverProfile) -> bool:
        if profile.packages:
            all_installed = True
            for pkg in profile.packages:
                if not self.manager.is_package_installed(pkg):
                    all_installed = False
                    break
            if all_installed:
                return True

        key_packages = []
        if profile.category == "Bluetooth":
            key_packages = ["parch-bluetooth", "bluez", "bluez-utils", "bluedevil", "blueman"]
        elif profile.category == "Network" or "NetworkManager" in profile.name:
            key_packages = ["networkmanager", "network-manager", "nm-connection-editor", "iwd", "broadcom-wl-dkms"]
        elif "NVIDIA" in profile.name:
            key_packages = ["nvidia-utils", "nvidia", "nvidia-open", "nvidia-open-dkms", "nvidia-prime"]
        elif "AMD" in profile.name:
            key_packages = ["xf86-video-amdgpu", "vulkan-radeon", "mesa"]
        elif "Intel" in profile.name:
            key_packages = ["xf86-video-intel", "vulkan-intel", "mesa"]

        for pkg in key_packages:
            if self.manager.is_package_installed(pkg):
                return True

        if profile.category == "Network" or "NetworkManager" in profile.name:
            code, out, _ = SystemProber.run_command(["systemctl", "is-active", "NetworkManager"])
            if code == 0:
                return True

        if profile.module:
            for dev in self.hardware_devices:
                if dev.get("driver") == profile.module:
                    return True
            if profile.module in ("btusb", "bluetooth"):
                if SystemProber.is_bluetooth_kernel_module_loaded() or SystemProber.is_bluetooth_service_running() or SystemProber.has_bluetooth_adapter():
                    return True

        return False

    def _is_module_disabled(self, module: str) -> bool:
        blacklist_path = "/etc/modprobe.d/parch-dm-blacklist.conf"
        if os.path.exists(blacklist_path):
            try:
                with open(blacklist_path, "r") as f:
                    content = f.read()
                    return f"blacklist {module}" in content
            except Exception:
                pass
        return False

    def _create_profile_widgets(self, profiles: List[DriverProfile], category: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        if not profiles:
            status_page = Adw.StatusPage()
            status_page.set_title(_("No profiles available"))
            status_page.set_description(_("No driver profiles were found for this category."))
            status_page.set_icon_name("dialog-information-symbolic")
            box.append(status_page)
            return box

        profiles_group = Adw.PreferencesGroup(title=_("Available Drivers"), description=_("Manage driver packages for this hardware category"))
        box.append(profiles_group)

        profile_listbox = Gtk.ListBox()
        profile_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        profile_listbox.add_css_class("boxed-list")
        profiles_group.add(profile_listbox)
        setattr(self, f"profile_listbox_{category.lower()}", profile_listbox)

        category_row_data = []
        for idx, profile in enumerate(profiles):
            row = Adw.ActionRow(title=profile.name, subtitle=profile.description)
            row_actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row_actions_box.set_valign(Gtk.Align.CENTER)
            row.add_suffix(row_actions_box)

            profile_listbox.append(row)
            category_row_data.append((row, profile, row_actions_box))

        self.profile_rows[category] = category_row_data
        self._refresh_profile_widgets(category)

        return box

    def _refresh_profile_widgets(self, category: str):
        row_data_list = self.profile_rows.get(category, [])
        for row, profile, actions_box in row_data_list:
            child = actions_box.get_first_child()
            while child is not None:
                next_child = child.get_next_sibling()
                actions_box.remove(child)
                child = next_child

            installed = self._is_profile_installed(profile)

            if installed:
                row.set_subtitle(f"{profile.description} • {_('Installed')}")

                status_badge = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
                status_badge.add_css_class("success-icon")
                actions_box.append(status_badge)

                if profile.module:
                    module_disabled = self._is_module_disabled(profile.module)
                    if module_disabled:
                        enable_btn = Gtk.Button(label=_("Enable"))
                        enable_btn.add_css_class("pill")
                        enable_btn.connect("clicked", lambda _, p=profile, c=category: self.on_enable_clicked_for_profile(p, c))
                        actions_box.append(enable_btn)
                    else:
                        disable_btn = Gtk.Button(label=_("Disable"))
                        disable_btn.add_css_class("pill")
                        disable_btn.connect("clicked", lambda _, p=profile, c=category: self.on_disable_clicked_for_profile(p, c))
                        actions_box.append(disable_btn)

                remove_btn = Gtk.Button(label=_("Remove"))
                remove_btn.add_css_class("destructive-action")
                remove_btn.add_css_class("pill")
                remove_btn.connect("clicked", lambda _, p=profile, c=category: self.on_remove_clicked_for_profile(p, c))
                actions_box.append(remove_btn)
            else:
                row.set_subtitle(profile.description)

                install_btn = Gtk.Button(label=_("Install"))
                install_btn.add_css_class("suggested-action")
                install_btn.add_css_class("pill")
                install_btn.connect("clicked", lambda _, p=profile, c=category: self.on_install_clicked_for_profile(p, c))
                actions_box.append(install_btn)

    def _build_gpu_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(840)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scrolled.set_child(clamp)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_vexpand(False)
        clamp.set_child(main_box)

        hw_group = Adw.PreferencesGroup(title=_("Detected Hardware"), description=_("Graphics adapters detected by system prober"))
        main_box.append(hw_group)

        hw_list = Gtk.ListBox()
        hw_list.add_css_class("boxed-list")
        hw_group.add(hw_list)

        gpus = [d for d in self.hardware_devices if d['category'] == 'GPU']
        if gpus:
            for gpu in gpus:
                driver_text = gpu['driver'] if gpu['driver'] else _('None')
                sub = f"{_('Driver in use')}: {driver_text}"
                row = Adw.ActionRow(title=gpu['name'], subtitle=sub)

                status_badge = Gtk.Image()
                if gpu['driver']:
                    status_badge.set_from_icon_name("emblem-ok-symbolic")
                    status_badge.add_css_class("success-icon")
                else:
                    status_badge.set_from_icon_name("dialog-warning-symbolic")
                    status_badge.add_css_class("warning-icon")
                row.add_prefix(status_badge)
                hw_list.append(row)
        else:
            hw_group.set_visible(False)
            status_page = Adw.StatusPage()
            status_page.set_title(_("No GPU detected"))
            status_page.set_icon_name("computer-symbolic")
            main_box.append(status_page)

        vendors = self.gpu_info.get("vendors", [self.gpu_info.get("vendor", "Unknown")])
        self.gpu_profiles = DriverProfiles.get_gpu_profiles(vendors, self.kernel_flavor)
        main_box.append(self._create_profile_widgets(self.gpu_profiles, "GPU"))

        self.stack.add_named(scrolled, _("GPU"))

    def _build_network_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(840)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scrolled.set_child(clamp)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_vexpand(False)
        clamp.set_child(main_box)

        hw_group = Adw.PreferencesGroup(title=_("Detected Hardware"), description=_("Network interfaces detected by system prober"))
        main_box.append(hw_group)

        hw_list = Gtk.ListBox()
        hw_list.add_css_class("boxed-list")
        hw_group.add(hw_list)

        nets = [d for d in self.hardware_devices if d['category'] == 'Network']
        if nets:
            for net in nets:
                driver_text = net['driver'] if net['driver'] else _('None')
                sub = f"{_('Driver in use')}: {driver_text}"
                row = Adw.ActionRow(title=net['name'], subtitle=sub)

                status_badge = Gtk.Image()
                if net['driver'] or self.manager.is_package_installed("networkmanager"):
                    status_badge.set_from_icon_name("emblem-ok-symbolic")
                    status_badge.add_css_class("success-icon")
                else:
                    status_badge.set_from_icon_name("dialog-warning-symbolic")
                    status_badge.add_css_class("warning-icon")
                row.add_prefix(status_badge)
                hw_list.append(row)
        else:
            hw_group.set_visible(False)
            status_page = Adw.StatusPage()
            status_page.set_title(_("No Network devices detected"))
            status_page.set_icon_name("network-wireless-symbolic")
            main_box.append(status_page)

        self.net_profiles = DriverProfiles.get_network_profiles()
        main_box.append(self._create_profile_widgets(self.net_profiles, "Network"))
        self.stack.add_named(scrolled, _("Network"))

    def _build_audio_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(840)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scrolled.set_child(clamp)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_vexpand(False)
        clamp.set_child(main_box)

        hw_group = Adw.PreferencesGroup(title=_("Detected Hardware"), description=_("Audio cards and controllers detected"))
        main_box.append(hw_group)

        hw_list = Gtk.ListBox()
        hw_list.add_css_class("boxed-list")
        hw_group.add(hw_list)

        auds = [d for d in self.hardware_devices if d['category'] == 'Audio']
        if auds:
            for aud in auds:
                driver_text = aud['driver'] if aud['driver'] else _('None')
                sub = f"{_('Driver in use')}: {driver_text}"
                row = Adw.ActionRow(title=aud['name'], subtitle=sub)

                status_badge = Gtk.Image()
                if aud['driver']:
                    status_badge.set_from_icon_name("emblem-ok-symbolic")
                    status_badge.add_css_class("success-icon")
                else:
                    status_badge.set_from_icon_name("dialog-warning-symbolic")
                    status_badge.add_css_class("warning-icon")
                row.add_prefix(status_badge)
                hw_list.append(row)
        else:
            hw_group.set_visible(False)
            status_page = Adw.StatusPage()
            status_page.set_title(_("No Audio devices detected"))
            status_page.set_icon_name("audio-card-symbolic")
            main_box.append(status_page)

        self.audio_profiles = DriverProfiles.get_audio_profiles()
        main_box.append(self._create_profile_widgets(self.audio_profiles, "Audio"))
        self.stack.add_named(scrolled, _("Audio"))

    def _build_bluetooth_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(840)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scrolled.set_child(clamp)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_vexpand(False)
        clamp.set_child(main_box)

        hw_group = Adw.PreferencesGroup(title=_("Detected Hardware"), description=_("Bluetooth controllers and USB adapters"))
        main_box.append(hw_group)

        hw_list = Gtk.ListBox()
        hw_list.add_css_class("boxed-list")
        hw_group.add(hw_list)

        bts = [d for d in self.hardware_devices if d['category'] == 'Bluetooth']
        if bts:
            for bt in bts:
                driver_text = bt['driver'] if bt['driver'] else _('btusb')
                sub = f"{_('Driver in use')}: {driver_text}"

                if bt.get('service_active') is False:
                    sub += f" | {_('No Bluetooth service running')}"
                elif bt.get('rfkill_status') == "soft-blocked":
                    sub += f" | {_('Bluetooth is soft-blocked')}"
                elif bt.get('rfkill_status') == "hard-blocked":
                    sub += f" | {_('Bluetooth is hard-blocked')}"

                row = Adw.ActionRow(title=bt['name'], subtitle=sub)

                status_badge = Gtk.Image()
                if bt['driver'] or SystemProber.is_bluetooth_service_running() or self.manager.is_package_installed("parch-bluetooth") or self.manager.is_package_installed("bluez"):
                    status_badge.set_from_icon_name("emblem-ok-symbolic")
                    status_badge.add_css_class("success-icon")
                else:
                    status_badge.set_from_icon_name("dialog-warning-symbolic")
                    status_badge.add_css_class("warning-icon")
                row.add_prefix(status_badge)
                hw_list.append(row)
        else:
            hw_group.set_visible(False)
            status_page = Adw.StatusPage()
            status_page.set_title(_("No Bluetooth devices detected"))
            status_page.set_icon_name("preferences-system-bluetooth-symbolic")
            main_box.append(status_page)

        self.bt_profiles = DriverProfiles.get_bluetooth_profiles()
        main_box.append(self._create_profile_widgets(self.bt_profiles, "Bluetooth"))
        self.stack.add_named(scrolled, _("Bluetooth"))

    def _build_info_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(840)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scrolled.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_vexpand(False)
        clamp.set_child(box)

        info_group = Adw.PreferencesGroup(title=_("Hardware Configuration"))
        box.append(info_group)

        cpu_row = Adw.ActionRow(title=_("Processor"))
        cpu_row.set_subtitle(self.system_info.get("cpu", "Unknown"))
        info_group.add(cpu_row)

        vendor_row = Adw.ActionRow(title=_("GPU"))
        gpu_text = self.gpu_info.get("vendor", "Unknown")
        if self.gpu_info.get("model"):
            gpu_text = f"{gpu_text} ({self.gpu_info.get('model')})"
        vendor_row.set_subtitle(gpu_text)
        info_group.add(vendor_row)

        memory_row = Adw.ActionRow(title=_("Memory"))
        memory_row.set_subtitle(self.system_info.get("memory", "Unknown"))
        info_group.add(memory_row)

        system_group = Adw.PreferencesGroup(title=_("System Environment"))
        box.append(system_group)

        if self.system_info.get("vendor") or self.system_info.get("model"):
            device_row = Adw.ActionRow(title=_("Device"))
            device_text = f"{self.system_info.get('vendor', '')} {self.system_info.get('model', '')}".strip()
            device_row.set_subtitle(device_text or "Unknown")
            system_group.add(device_row)

        os_row = Adw.ActionRow(title=_("Operating System"))
        os_row.set_subtitle(self.system_info.get("os", "Parch GNU/Linux"))
        system_group.add(os_row)

        kernel_row = Adw.ActionRow(title=_("Kernel"))
        kernel_row.set_subtitle(self.kernel_info.get("version", "Unknown"))
        system_group.add(kernel_row)

        hostname_row = Adw.ActionRow(title=_("Hostname"))
        hostname_row.set_subtitle(self.system_info.get("hostname", "Unknown"))
        system_group.add(hostname_row)

        session_row = Adw.ActionRow(title=_("Display Server"))
        session_row.set_subtitle(self.session_type.upper())
        system_group.add(session_row)

        features_group = Adw.PreferencesGroup(title=_("Platform Features"))
        box.append(features_group)

        hybrid_row = Adw.ActionRow(title=_("Hybrid Graphics"))
        hybrid_status = _("Enabled") if self.hybrid else _("Disabled")
        hybrid_row.set_subtitle(hybrid_status)
        features_group.add(hybrid_row)

        secure_row = Adw.ActionRow(title=_("Secure Boot"))
        secure_status = _("Enabled") if self.secure_boot else _("Disabled")
        secure_row.set_subtitle(secure_status)
        features_group.add(secure_row)

        self.stack.add_named(scrolled, _("System Info"))

    def _build_logs_page(self):
        scrolled_outer = Gtk.ScrolledWindow()
        scrolled_outer.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_outer.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(840)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(16)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scrolled_outer.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        clamp.set_child(box)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.append(header_box)

        log_label = Gtk.Label(label=_("Operation Log"))
        log_label.set_xalign(0)
        log_label.add_css_class("title-3")
        log_label.set_hexpand(True)
        header_box.append(log_label)

        clear_button = Gtk.Button(label=_("Clear Logs"))
        clear_button.set_icon_name("edit-clear-symbolic")
        clear_button.add_css_class("flat")
        clear_button.connect("clicked", self.on_clear_logs)
        header_box.append(clear_button)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(320)
        scrolled.add_css_class("card")
        box.append(scrolled)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_view.set_top_margin(12)
        self.log_view.set_bottom_margin(12)
        self.log_view.set_left_margin(12)
        self.log_view.set_right_margin(12)
        scrolled.set_child(self.log_view)

        self.log_buffer = LogBuffer(self.log_view)

        self.stack.add_named(scrolled_outer, _("Logs"))

    def on_sidebar_selected(self, listbox, row):
        if row:
            title = row.get_title()
            subtitles = {
                _("GPU"): _("Graphics Drivers"),
                _("Network"): _("Network Interfaces"),
                _("Audio"): _("Audio Stack"),
                _("Bluetooth"): _("Bluetooth Services"),
                _("System Info"): _("Hardware and OS Details"),
                _("Logs"): _("Activity and Event Logs")
            }
            subtitle = subtitles.get(title, _("Parch Driver Manager"))
            self.content_window_title.set_title(title)
            self.content_window_title.set_subtitle(subtitle)
            self.stack.set_visible_child_name(title)
            self.current_category = title

            # Close overlay sidebar automatically in mobile collapsed mode
            if self.split_view.get_collapsed():
                self.split_view.set_show_sidebar(False)

    def _progress_callback(self, msg: str):
        self.log_buffer.append(msg)

    def _run_in_thread(self, target: Callable, *args, **kwargs):
        if self.current_operation and self.current_operation.is_alive():
            self._show_toast(_("An operation is already in progress."), timeout=4)
            return

        def wrapper():
            try:
                target(*args, **kwargs)
            except CommandError as e:
                msg = f"❌ Command error: {' '.join(e.cmd)}\nExit code: {e.returncode}\n{e.stderr}"
                logger.error(msg)
                GLib.idle_add(self._show_toast, f"{_('Operation failed')}: {e.stderr.strip() or 'Exit code ' + str(e.returncode)}", 6)
                GLib.idle_add(self._end_operation)
                self.log_buffer.append(msg)
            except Exception as e:
                msg = f"❌ Unexpected error: {e}"
                logger.error(msg, exc_info=True)
                GLib.idle_add(self._show_toast, f"{_('Unexpected error')}: {e}", 6)
                GLib.idle_add(self._end_operation)
                self.log_buffer.append(msg)
            finally:
                self.current_operation = None

        self.current_operation = threading.Thread(target=wrapper, daemon=True)
        self.current_operation.start()

    def _start_operation(self):
        self.progress_bar.set_visible(True)
        self.progress_bar.pulse()
        if self._progress_timeout_id:
            GLib.source_remove(self._progress_timeout_id)
        self._progress_timeout_id = GLib.timeout_add(100, self._pulse_progress)
        self.set_sensitive(False)

    def _pulse_progress(self):
        if self.progress_bar.get_visible():
            self.progress_bar.pulse()
            return True
        self._progress_timeout_id = None
        return False

    def _end_operation(self):
        self.progress_bar.set_visible(False)
        if self._progress_timeout_id:
            GLib.source_remove(self._progress_timeout_id)
            self._progress_timeout_id = None
        self.set_sensitive(True)

    def on_clear_logs(self, button):
        buffer = self.log_view.get_buffer()
        buffer.set_text("")

    def _load_css(self):
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "style.css")
        if os.path.exists(css_path):
            css_provider.load_from_path(css_path)
        else:
            css = """
            .navigation-sidebar row { min-height: 44px; padding: 6px 12px; }
            .success-icon { color: @success_color; }
            .warning-icon { color: @warning_color; }
            .card { background: @card_bg_color; border-radius: 12px; padding: 4px; }
            .pill { border-radius: 9999px; padding: 4px 16px; font-weight: 600; }
            """
            css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_refresh_hardware(self, _button=None):
        def refresh():
            GLib.idle_add(self._start_operation)
            SystemProber.clear_hw_cache()
            self._probe_hardware()
            GLib.idle_add(self._rebuild_all_pages)
            GLib.idle_add(self._populate_sidebar)
            GLib.idle_add(self._end_operation)
            GLib.idle_add(self._show_toast, _("Hardware detection refreshed."))

        self._run_in_thread(refresh)

    def _on_alert_response(self, dialog, result, action):
        response = dialog.choose_finish(result)
        if response != "confirm":
            return
        action()

    def _show_confirm_dialog(self, heading: str, body: str, on_confirm: Callable, destructive: bool = False):
        dialog = Adw.AlertDialog.new(heading, body)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("confirm", _("Confirm"))
        if destructive:
            dialog.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
        else:
            dialog.set_response_appearance("confirm", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.choose(self, None, self._on_alert_response, on_confirm)

    def on_install_clicked_for_profile(self, profile: DriverProfile, category: str):
        self._show_confirm_dialog(
            _("Are you sure?"),
            f"{_('This action will install driver packages for')} {profile.name}.",
            lambda: self._do_install(profile, category),
        )

    def _do_install(self, profile: DriverProfile, category: str):
        def task():
            GLib.idle_add(self._start_operation)
            self.log_buffer.append(f"➔ {_('Starting installation')}: {profile.name}")
            self.manager.install_profile(profile, progress_cb=self._progress_callback)
            self.log_buffer.append(f"✓ {_('Profile installation finished.')}")
            GLib.idle_add(self._refresh_profile_widgets, category)
            GLib.idle_add(self._populate_sidebar)
            GLib.idle_add(self._end_operation)
            GLib.idle_add(self._show_toast, _("Profile installed successfully."))

        self._run_in_thread(task)

    def on_remove_clicked_for_profile(self, profile: DriverProfile, category: str):
        self._show_confirm_dialog(
            _("Are you sure?"),
            f"{_('This action will remove driver packages for')} {profile.name}.",
            lambda: self._do_remove(profile, category),
            destructive=True,
        )

    def _do_remove(self, profile: DriverProfile, category: str):
        def task():
            GLib.idle_add(self._start_operation)
            self.log_buffer.append(f"➔ {_('Starting removal')}: {profile.name}")
            self.manager.remove_profile(profile, progress_cb=self._progress_callback)
            self.log_buffer.append(f"✓ {_('Profile removal finished.')}")
            GLib.idle_add(self._refresh_profile_widgets, category)
            GLib.idle_add(self._populate_sidebar)
            GLib.idle_add(self._end_operation)
            GLib.idle_add(self._show_toast, _("Profile removed successfully."))

        self._run_in_thread(task)

    def on_disable_clicked_for_profile(self, profile: DriverProfile, category: str):
        self._show_confirm_dialog(
            _("Are you sure?"),
            f"{_('This action will disable module')} {profile.module}.",
            lambda: self._do_disable(profile, category),
            destructive=True,
        )

    def _do_disable(self, profile: DriverProfile, category: str):
        def task():
            GLib.idle_add(self._start_operation)
            self.log_buffer.append(f"➔ {_('Disabling hardware module')}: {profile.name}")
            self.manager.disable_driver(profile, progress_cb=self._progress_callback)
            GLib.idle_add(self._refresh_profile_widgets, category)
            GLib.idle_add(self._populate_sidebar)
            GLib.idle_add(self._end_operation)
            GLib.idle_add(self._show_toast, _("Hardware disabled. Reboot might be required."))

        self._run_in_thread(task)

    def on_enable_clicked_for_profile(self, profile: DriverProfile, category: str):
        self._show_confirm_dialog(
            _("Are you sure?"),
            f"{_('This action will enable module')} {profile.module}.",
            lambda: self._do_enable(profile, category),
        )

    def _do_enable(self, profile: DriverProfile, category: str):
        def task():
            GLib.idle_add(self._start_operation)
            self.log_buffer.append(f"➔ {_('Enabling hardware module')}: {profile.name}")
            self.manager.enable_driver(profile, progress_cb=self._progress_callback)
            GLib.idle_add(self._refresh_profile_widgets, category)
            GLib.idle_add(self._populate_sidebar)
            GLib.idle_add(self._end_operation)
            GLib.idle_add(self._show_toast, _("Hardware enabled."))

        self._run_in_thread(task)

    def _show_toast(self, text: str, timeout: int = 3):
        toast = Adw.Toast.new(text)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)
