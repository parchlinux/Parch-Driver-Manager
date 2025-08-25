import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

import subprocess
import sys
import threading
from typing import List, Dict, Any, Callable, Optional, Tuple

class SystemProber:
    @staticmethod
    def run_command(command: List[str]) -> Optional[str]:
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    @staticmethod
    def get_gpu_info() -> Dict[str, str]:
        vendor, model = "Unknown", "N/A"
        output = SystemProber.run_command(["lspci", "-nnk"])
        if not output: return {"vendor": vendor, "model": model}
        for line in output.splitlines():
            if "VGA compatible controller" in line or "3D controller" in line:
                model = line.split(":", 2)[-1].strip()
                if "NVIDIA" in model: vendor = "NVIDIA"
                elif "AMD/ATI" in model: vendor = "AMD"
                elif "Intel" in model: vendor = "Intel"
                break
        return {"vendor": vendor, "model": model}

    @staticmethod
    def get_pci_device_info(pattern: str) -> str:
        output = SystemProber.run_command(["lspci"])
        if not output: return "Not detected"
        for line in output.splitlines():
            if pattern.lower() in line.lower():
                return line.split(":", 2)[-1].strip()
        return "Not detected"

    @staticmethod
    def get_kernel_identifier() -> str:
        uname_r = SystemProber.run_command(["uname", "-r"]) or ""
        if "lts" in uname_r: return "lts"
        if "zen" in uname_r: return "zen"
        if "hardened" in uname_r: return "hardened"
        return "mainline"

    @staticmethod
    def is_module_loaded(module_name: str) -> bool:
        output = SystemProber.run_command(["lsmod"])
        return any(line.startswith(module_name) for line in (output or "").splitlines())

    @staticmethod
    def is_service_active(service_name: str) -> bool:
        try:
            result = subprocess.run(["systemctl", "is-active", service_name], capture_output=True, text=True)
            return result.stdout.strip() == "active"
        except FileNotFoundError:
            return False

class DriverProfiles:
    KERNEL_HEADERS = { "mainline": "linux-headers", "lts": "linux-lts-headers", "zen": "linux-zen-headers", "hardened": "linux-hardened-headers" }
    
    @staticmethod
    def get_profiles(kernel_id: str) -> Dict[str, Any]:
        headers = DriverProfiles.KERNEL_HEADERS.get(kernel_id, "linux-headers")
        return {
            "NVIDIA": [{ "id": "nvidia-proprietary", "name": "Proprietary NVIDIA Driver", "description": "Maximum performance for gaming and professional applications.", "packages": ["base-devel", headers, "nvidia-dkms", "nvidia-utils", "lib32-nvidia-utils", "nvidia-settings"], "conflicts": ["xf86-video-nouveau"], "is_active": lambda: SystemProber.is_module_loaded("nvidia"), "post_install_commands": ["echo 'blacklist nouveau' | tee /etc/modprobe.d/nvidia.conf"]},
                       { "id": "nvidia-opensource", "name": "Open-Source Driver (Nouveau)", "description": "Basic desktop usage, not for modern gaming.", "packages": ["xf86-video-nouveau"], "conflicts": ["nvidia-dkms", "nvidia-utils", "lib32-nvidia-utils", "nvidia-settings"], "is_active": lambda: SystemProber.is_module_loaded("nouveau"), "post_install_commands": ["rm -f /etc/modprobe.d/nvidia.conf"]}],
            "AMD": [{ "id": "amd-opensource", "name": "Open-Source Mesa Drivers", "description": "Excellent performance for gaming on AMD GPUs.", "packages": ["mesa", "lib32-mesa", "vulkan-radeon", "lib32-vulkan-radeon", "libva-mesa-driver", "mesa-vdpau"], "conflicts": [], "is_active": lambda: SystemProber.is_module_loaded("amdgpu")}],
            "Intel": [{ "id": "intel-opensource", "name": "Open-Source Mesa Drivers", "description": "Complete open-source stack for Intel GPUs.", "packages": ["mesa", "lib32-mesa", "vulkan-intel", "lib32-vulkan-intel", "intel-media-driver"], "conflicts": [], "is_active": lambda: SystemProber.is_module_loaded("i915")}]
        }

class CommandRunnerThread(threading.Thread):
    def __init__(self, command: str, on_line: Callable[[str], None], on_done: Callable[[int], None]):
        super().__init__(daemon=True)
        self.command, self.on_line, self.on_done = command, on_line, on_done
    def run(self):
        try:
            proc = subprocess.Popen(["pkexec", "bash", "-c", self.command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True, encoding='utf-8')
            if proc.stdout:
                for line in proc.stdout: GLib.idle_add(self.on_line, line.strip())
            rc = proc.wait()
            GLib.idle_add(self.on_done, rc)
        except Exception as e:
            GLib.idle_add(self.on_line, f"Fatal error: {e}")
            GLib.idle_add(self.on_done, -1)

class PersianArchDriverManager(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(1100, 800)
        self.set_title("Persian Arch Driver Manager")
        self._build_ui()
        self.refresh_all_info()

    def _build_ui(self):
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_vbox)
        self.header = Adw.HeaderBar()
        self.spinner = Gtk.Spinner()
        refresh_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_button.connect("clicked", self.refresh_all_info)
        self.header.pack_start(self.spinner)
        self.header.pack_end(refresh_button)
        main_vbox.append(self.header)
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_vexpand(True)
        main_vbox.append(self.toast_overlay)
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.toast_overlay.set_child(main_hbox)
        self.stack_sidebar = Gtk.StackSidebar()
        main_hbox.append(self.stack_sidebar)
        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)
        self.stack_sidebar.set_stack(self.stack)
        main_hbox.append(self.stack)
        
        self._create_page("graphics", "Graphics Card", "video-card-symbolic", self._build_graphics_page)
        self._create_page("audio", "Audio Device", "audio-card-symbolic", self._build_audio_page)
        self._create_page("network", "Network Controller", "network-wired-symbolic", self._build_network_page)
        self._create_page("bluetooth", "Bluetooth", "bluetooth-symbolic", self._build_bluetooth_page)

    def _create_page(self, name: str, title: str, icon_name: str, build_fn: Callable):
        page_widget, log_buffer = build_fn()
        setattr(self, f"{name}_log_buffer", log_buffer)
        page = self.stack.add_named(page_widget, name)
        page.set_title(title)
        page.set_icon_name(icon_name)

    def _create_page_layout(self) -> Tuple[Gtk.Widget, Gtk.Box, Gtk.TextBuffer]:
        main_split = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL, wide_handle=True)
        clamp = Adw.Clamp(margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        scrolled_window = Gtk.ScrolledWindow(child=clamp, vexpand=True)
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_split.set_start_child(scrolled_window)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        clamp.set_child(content_box)
        
        log_view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        log_view.add_css_class("card")
        log_scroller = Gtk.ScrolledWindow(child=log_view)
        log_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        log_scroller.set_min_content_height(250)
        main_split.set_end_child(log_scroller)
        main_split.set_position(450)
        
        return main_split, content_box, log_view.get_buffer()

    def _build_graphics_page(self) -> Tuple[Gtk.Widget, Gtk.TextBuffer]:
        container, page_box, log_buffer = self._create_page_layout()
        
        prop_group = Adw.PreferencesGroup(title="Detected Graphics Device")
        page_box.append(prop_group)
        self.gpu_model_row = Adw.ActionRow(title="Model")
        prop_group.add(self.gpu_model_row)
        self.gpu_driver_row = Adw.ActionRow(title="Active Driver")
        prop_group.add(self.gpu_driver_row)
        self.actions_group_container = Adw.PreferencesGroup(title="Available Drivers")
        page_box.append(self.actions_group_container)
        self.apply_button_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER)
        page_box.append(self.apply_button_container)
        return container, log_buffer

    def _build_audio_page(self) -> Tuple[Gtk.Widget, Gtk.TextBuffer]:
        container, page_box, log_buffer = self._create_page_layout()

        prop_group = Adw.PreferencesGroup(title="Device Properties")
        page_box.append(prop_group)
        self.audio_device_row = Adw.ActionRow(title="Device")
        prop_group.add(self.audio_device_row)
        action_group = Adw.PreferencesGroup(title="Available Actions")
        page_box.append(action_group)
        install_button = Gtk.Button(label="Install Core Audio Packages", halign=Gtk.Align.START)
        install_button.connect("clicked", self._on_install_audio)
        install_button.add_css_class("pill")
        row = Adw.ActionRow()
        row.set_activatable_widget(install_button)
        row.add_suffix(install_button)
        action_group.add(row)
        return container, log_buffer

    def _build_network_page(self) -> Tuple[Gtk.Widget, Gtk.TextBuffer]:
        container, page_box, log_buffer = self._create_page_layout()

        prop_group = Adw.PreferencesGroup(title="Device Properties")
        page_box.append(prop_group)
        self.network_device_row = Adw.ActionRow(title="Device")
        prop_group.add(self.network_device_row)
        self.nm_status_row = Adw.ActionRow(title="NetworkManager Service")
        prop_group.add(self.nm_status_row)
        action_group = Adw.PreferencesGroup(title="Available Actions")
        page_box.append(action_group)
        install_button = Gtk.Button(label="Install and Enable NetworkManager", halign=Gtk.Align.START)
        install_button.connect("clicked", self._on_install_network)
        install_button.add_css_class("pill")
        row = Adw.ActionRow()
        row.set_activatable_widget(install_button)
        row.add_suffix(install_button)
        action_group.add(row)
        return container, log_buffer

    def _build_bluetooth_page(self) -> Tuple[Gtk.Widget, Gtk.TextBuffer]:
        container, page_box, log_buffer = self._create_page_layout()

        prop_group = Adw.PreferencesGroup(title="Device Properties")
        page_box.append(prop_group)
        self.bt_status_row = Adw.ActionRow(title="Bluetooth Service")
        prop_group.add(self.bt_status_row)
        action_group = Adw.PreferencesGroup(title="Available Actions")
        page_box.append(action_group)
        install_button = Gtk.Button(label="Install and Enable Bluetooth", halign=Gtk.Align.START)
        install_button.connect("clicked", self._on_install_bluetooth)
        install_button.add_css_class("pill")
        row = Adw.ActionRow()
        row.set_activatable_widget(install_button)
        row.add_suffix(install_button)
        action_group.add(row)
        return container, log_buffer

    def refresh_all_info(self, *args):
        self.set_busy(True)
        GLib.idle_add(self.perform_refresh)

    def perform_refresh(self):
        gpu_info = SystemProber.get_gpu_info()
        self.gpu_vendor = gpu_info["vendor"]
        kernel_id = SystemProber.get_kernel_identifier()
        self.driver_profiles = DriverProfiles.get_profiles(kernel_id)
        self.gpu_model_row.set_subtitle(gpu_info["model"])
        self._update_gpu_actions()

        self.audio_device_row.set_subtitle(SystemProber.get_pci_device_info("Audio"))
        self.network_device_row.set_subtitle(SystemProber.get_pci_device_info("Network") or SystemProber.get_pci_device_info("Ethernet"))
        self.nm_status_row.set_subtitle("Active" if SystemProber.is_service_active("NetworkManager") else "Inactive")
        self.bt_status_row.set_subtitle("Active" if SystemProber.is_service_active("bluetooth") else "Inactive")
        self.set_busy(False)
        return GLib.SOURCE_REMOVE

    def _update_gpu_actions(self):
        for child in list(self.actions_group_container): self.actions_group_container.remove(child)
        for child in list(self.apply_button_container): self.apply_button_container.remove(child)
        vendor_profiles = self.driver_profiles.get(self.gpu_vendor, [])
        active_group, current_driver_name = None, "Unknown"
        if not vendor_profiles:
            self.actions_group_container.set_title("No Drivers Available")
            self.gpu_driver_row.set_subtitle("N/A")
            return
        self.actions_group_container.set_title(f"Drivers for {self.gpu_vendor}")
        for i, profile in enumerate(vendor_profiles):
            is_active = profile["is_active"]()
            row = Adw.ActionRow(title=profile["name"], subtitle=profile["description"])
            radio = Gtk.CheckButton(group=active_group)
            if i == 0: active_group = radio
            radio.set_active(is_active)
            radio.set_can_focus(not is_active)
            radio.connect("toggled", self.on_driver_selected, profile)
            row.add_prefix(radio)
            self.actions_group_container.add(row)
            if is_active: current_driver_name = profile["name"]
        self.gpu_driver_row.set_subtitle(current_driver_name)
        apply_button = Gtk.Button(label="Apply Changes", halign=Gtk.Align.CENTER)
        apply_button.add_css_class("pill suggested-action")
        apply_button.set_sensitive(False)
        apply_button.connect("clicked", self._on_apply_graphics_clicked)
        self.apply_button = apply_button
        self.apply_button_container.append(apply_button)

    def on_driver_selected(self, radio, profile):
        if radio.get_active():
            self.selected_profile = profile
            self.apply_button.set_sensitive(not profile["is_active"]())

    def _on_apply_graphics_clicked(self, _):
        dialog = Adw.MessageDialog(heading="Confirm Driver Change", body="Changing graphics drivers is a critical system operation that requires a reboot.\n\nIt is strongly recommended to back up your system before proceeding.\n\nAre you sure you want to continue?", transient_for=self)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("confirm", "Confirm and Apply")
        dialog.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_confirm_apply_graphics)
        dialog.present()

    def on_confirm_apply_graphics(self, dialog, response_id):
        dialog.close()
        if response_id != "confirm" or not hasattr(self, 'selected_profile') or self.selected_profile is None: return
        profile = self.selected_profile
        install = " ".join(profile["packages"])
        remove = " ".join(profile["conflicts"])
        post_cmds = profile.get("post_install_commands", [])
        cmds = ["set -e", "echo '==> Synchronizing system packages...'", "pacman -Syu --noconfirm"]
        if remove: cmds.extend([f"echo '==> Removing conflicting packages: {remove}...' ", f"pacman -Rns --noconfirm {remove}"])
        if install: cmds.extend([f"echo '==> Installing selected driver packages: {install}...' ", f"pacman -S --noconfirm --needed {install}"])
        if post_cmds: cmds.extend(["echo '==> Running post-installation tasks...'"] + post_cmds)
        cmds.extend(["echo '==> Updating initramfs (boot image)...'", "mkinitcpio -P"])
        self._run_action(self.graphics_log_buffer, f"Install {profile['name']}", " && ".join(cmds))

    def _on_install_audio(self, _):
        cmd = "set -e && pacman -Syu --noconfirm && pacman -S --noconfirm --needed pipewire-pulse alsa-utils"
        self._run_action(self.audio_log_buffer, "Install Core Audio Packages", cmd)

    def _on_install_network(self, _):
        cmd = "set -e && pacman -Syu --noconfirm && pacman -S --noconfirm --needed networkmanager && systemctl enable --now NetworkManager.service"
        self._run_action(self.network_log_buffer, "Install NetworkManager", cmd)

    def _on_install_bluetooth(self, _):
        cmd = "set -e && pacman -Syu --noconfirm && pacman -S --noconfirm --needed bluez bluez-utils && systemctl enable --now bluetooth.service"
        self._run_action(self.bluetooth_log_buffer, "Install Bluetooth Stack", cmd)

    def set_busy(self, busy: bool):
        self.spinner.set_spinning(busy)
        self.stack.set_sensitive(not busy)
        self.stack_sidebar.set_sensitive(not busy)

    def append_log(self, buffer: Gtk.TextBuffer, text: str):
        buffer.insert(buffer.get_end_iter(), text + "\n")

    def _run_action(self, log_buffer: Gtk.TextBuffer, title: str, command: str):
        log_buffer.set_text("")
        self.set_busy(True)
        self.append_log(log_buffer, f"🚀 Starting task: {title}")
        self.append_log(log_buffer, "-" * 60)
        runner = CommandRunnerThread(command, lambda line: self.append_log(log_buffer, line), lambda rc: self._on_action_done(title, rc))
        runner.start()

    def _on_action_done(self, title: str, return_code: int):
        current_log_buffer = getattr(self, f"{self.stack.get_visible_child_name()}_log_buffer", None)
        if current_log_buffer:
            if return_code == 0:
                self.append_log(current_log_buffer, "\n" + "-" * 60)
                msg = "✅ Success! A reboot is required for changes to take full effect." if "NVIDIA" in title else "✅ Operation completed successfully."
                self.append_log(current_log_buffer, msg)
                self.toast_overlay.add_toast(Adw.Toast(title=msg.lstrip("✅ "), timeout=8))
            else:
                self.append_log(current_log_buffer, "\n" + "-" * 60)
                msg = "❌ Operation Failed. Check logs for details."
                self.append_log(current_log_buffer, msg)
                self.toast_overlay.add_toast(Adw.Toast(title=msg.lstrip("❌ "), timeout=10))
        
        self.set_busy(False)
        self.refresh_all_info()

class Application(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        win = PersianArchDriverManager(application=app)
        win.present()

if __name__ == "__main__":
    app = Application(application_id="com.persianarch.DriverManager")
    app.run(sys.argv)
