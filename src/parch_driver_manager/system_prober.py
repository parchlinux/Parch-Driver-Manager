import logging
import os
import subprocess
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class CommandError(Exception):
    def __init__(self, cmd: List[str], returncode: int, stdout: str, stderr: str):
        super().__init__(f"Command failed: {' '.join(cmd)} (code {returncode})")
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class SystemProber:
    _lspci_cache: Optional[str] = None
    _hw_cache: Optional[List[Dict[str, Any]]] = None

    @staticmethod
    def run_command(command: List[str], check: bool = False) -> Tuple[int, str, str]:
        logger.debug("Running command: %s", ' '.join(command))
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = proc.communicate()
        if check and proc.returncode != 0:
            raise CommandError(command, proc.returncode, out, err)
        return proc.returncode, out, err

    @staticmethod
    def get_lspci(force: bool = False) -> str:
        if SystemProber._lspci_cache is not None and not force:
            logger.debug("Using cached lspci output")
            return SystemProber._lspci_cache
        code, out, err = SystemProber.run_command(["lspci", "-nnk"])
        if code != 0:
            logger.debug("lspci failed: %s", err.strip())
            return ""
        SystemProber._lspci_cache = out
        return out

    @staticmethod
    def clear_lspci_cache() -> None:
        SystemProber._lspci_cache = None
        SystemProber._hw_cache = None

    @staticmethod
    def get_usb_devices() -> List[Dict[str, Any]]:
        code, out, err = SystemProber.run_command(["lsusb"])
        if code != 0:
            return []
        bt_module_loaded = SystemProber.is_bluetooth_kernel_module_loaded()
        devices = []
        seen = set()
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split(None, 6)
            if len(parts) < 6:
                continue
            name = parts[-1] if len(parts) > 6 else parts[5] if len(parts) > 5 else ""
            lower = name.lower()
            if 'bluetooth' in lower or lower.endswith('bt'):
                key = f"bluetooth_usb_{name}"
                if key in seen:
                    continue
                seen.add(key)
                driver = 'btusb' if bt_module_loaded else None
                devices.append({
                    'pci': '',
                    'name': name,
                    'category': 'Bluetooth',
                    'driver': driver,
                    'modules': ['btusb'] if bt_module_loaded else [],
                    'bus': 'usb',
                })
            elif 'wireless' in lower or 'wifi' in lower or 'wlan' in lower:
                key = f"net_usb_{name}"
                if key in seen:
                    continue
                seen.add(key)
                devices.append({
                    'pci': '',
                    'name': name,
                    'category': 'Network',
                    'driver': None,
                    'modules': [],
                    'bus': 'usb',
                })
        return devices

    @staticmethod
    def is_bluetooth_service_running() -> bool:
        code, _, _ = SystemProber.run_command(["systemctl", "is-active", "bluetooth"])
        return code == 0

    @staticmethod
    def is_bluetooth_kernel_module_loaded() -> bool:
        code, out, _ = SystemProber.run_command(["lsmod"])
        if code == 0:
            for line in out.splitlines():
                if line.startswith("btusb") or line.startswith("bluetooth"):
                    return True
        return False

    @staticmethod
    def get_bluetooth_rfkill_status() -> Optional[str]:
        code, out, _ = SystemProber.run_command(["rfkill", "list"])
        if code != 0:
            return None
        soft_blocked = False
        hard_blocked = False
        in_bt = False
        for line in out.splitlines():
            lowered = line.lower()
            if "bluetooth" in lowered and ":" in line.split(":")[0]:
                in_bt = True
                continue
            if in_bt:
                stripped = line.strip()
                if "soft blocked:" in stripped:
                    if "yes" in stripped.split(":")[-1]:
                        soft_blocked = True
                    else:
                        pass
                elif "hard blocked:" in stripped:
                    if "yes" in stripped.split(":")[-1]:
                        hard_blocked = True
                    in_bt = False
        if hard_blocked:
            return "hard-blocked"
        if soft_blocked:
            return "soft-blocked"
        return "unblocked"

    @staticmethod
    def has_bluetooth_adapter() -> bool:
        if os.path.isdir("/sys/class/bluetooth") and os.listdir("/sys/class/bluetooth"):
            return True
        return False

    @staticmethod
    def clear_hw_cache() -> None:
        SystemProber._hw_cache = None
        SystemProber._lspci_cache = None

    @staticmethod
    def get_hardware_devices(force: bool = False) -> List[Dict[str, Any]]:
        if SystemProber._hw_cache is not None and not force:
            return SystemProber._hw_cache
        lspci = SystemProber.get_lspci()
        devices = []
        current_dev = {}

        for line in lspci.splitlines():
            if not line.startswith('\t') and not line.startswith(' ') and line.strip():
                if current_dev:
                    devices.append(current_dev)

                parts = line.split(': ', 1)
                if len(parts) == 2:
                    pci_id = parts[0].split(' ')[0]
                    device_desc = parts[1]
                    device_type = parts[0].split(': ')[0] if ': ' in parts[0] else ''

                    current_dev = {
                        'pci': pci_id,
                        'name': device_desc,
                        'category': 'Other',
                        'driver': None,
                        'modules': []
                    }

                    lower_line = line.lower()

                    if 'vga compatible controller' in lower_line or '3d controller' in lower_line or 'display controller' in lower_line:
                        current_dev['category'] = 'GPU'
                    elif 'audio device' in lower_line or 'audio controller' in lower_line or 'multimedia audio' in lower_line:
                        current_dev['category'] = 'Audio'
                    elif 'network controller' in lower_line or 'ethernet controller' in lower_line or 'wireless' in lower_line:
                        current_dev['category'] = 'Network'
                    elif 'bluetooth' in lower_line:
                        current_dev['category'] = 'Bluetooth'
            else:
                line = line.strip()
                if line.startswith('Kernel driver in use:'):
                    driver = line.split(':', 1)[1].strip()
                    current_dev['driver'] = driver
                elif line.startswith('Kernel modules:'):
                    modules_str = line.split(':', 1)[1].strip()
                    current_dev['modules'] = [m.strip() for m in modules_str.split(',')]

        if current_dev:
            devices.append(current_dev)

        usb_devices = SystemProber.get_usb_devices()
        bt_rfkill = SystemProber.get_bluetooth_rfkill_status()
        bt_service = SystemProber.is_bluetooth_service_running()
        bt_module = SystemProber.is_bluetooth_kernel_module_loaded()

        for usb_dev in usb_devices:
            if usb_dev['category'] == 'Bluetooth':
                usb_dev['rfkill_status'] = bt_rfkill
                usb_dev['service_active'] = bt_service

        existing_categories = {d['category'] for d in devices}
        for usb_dev in usb_devices:
            if usb_dev['category'] not in existing_categories:
                devices.append(usb_dev)
                existing_categories.add(usb_dev['category'])

        bt_present = any(d['category'] == 'Bluetooth' for d in devices)
        if not bt_present and SystemProber.has_bluetooth_adapter():
            devices.append({
                'pci': '',
                'name': 'Bluetooth Adapter',
                'category': 'Bluetooth',
                'driver': 'btusb' if bt_module else None,
                'modules': ['btusb'] if bt_module else [],
                'bus': 'sysfs',
                'rfkill_status': bt_rfkill,
                'service_active': bt_service,
            })

        SystemProber._hw_cache = devices
        return devices

    @staticmethod
    def get_gpu_info() -> Dict[str, Any]:
        lspci = SystemProber.get_lspci()
        vendors = set()
        models = []

        for line in lspci.splitlines():
            lower = line.lower()
            if ("vga compatible controller" in lower or
                "3d controller" in lower or
                "display controller" in lower):
                vendor = None
                if "intel corporation" in lower or "[8086:" in lower:
                    vendor = "Intel"
                elif "nvidia" in lower or "[10de:" in lower:
                    vendor = "NVIDIA"
                elif ("amd" in lower or "ati" in lower or
                      "advanced micro devices" in lower or "[1002:" in lower):
                    vendor = "AMD"

                if vendor:
                    vendors.add(vendor)

                if ':' in line and ']' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        model = parts[1].split('[')[0].strip()
                        if model and model not in models:
                            models.append(model)

        vendor_list = sorted(list(vendors))
        main_vendor = ", ".join(vendor_list) if vendor_list else "Unknown"
        gpu_model = ", ".join(models) if models else ""

        return {"vendor": main_vendor, "vendors": vendor_list, "model": gpu_model, "raw": lspci}

    @staticmethod
    def get_session_type() -> str:
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session_type in ("wayland", "x11"):
            return session_type
        if os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        if os.environ.get("DISPLAY"):
            return "x11"
        return "unknown"

    @staticmethod
    def is_hybrid_graphics() -> bool:
        devices = SystemProber.get_hardware_devices()
        gpus = [d for d in devices if d['category'] == 'GPU']

        if len(gpus) < 2:
            return False

        vendors = set()
        for gpu in gpus:
            name_lower = gpu['name'].lower()
            if 'nvidia' in name_lower:
                vendors.add('nvidia')
            elif 'intel' in name_lower:
                vendors.add('intel')
            elif 'amd' in name_lower or 'ati' in name_lower or 'radeon' in name_lower:
                vendors.add('amd')

        return len(vendors) >= 2

    @staticmethod
    def get_kernel_info() -> Dict[str, str]:
        code, out, err = SystemProber.run_command(["uname", "-r"])
        kernel_version = out.strip() if code == 0 else "Unknown"

        kernel_flavor = "default"
        if "-lts" in kernel_version:
            kernel_flavor = "lts"
        elif "-zen" in kernel_version:
            kernel_flavor = "zen"
        elif "-hardened" in kernel_version:
            kernel_flavor = "hardened"

        return {
            "version": kernel_version,
            "flavor": kernel_flavor
        }

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        info = {}

        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        info['cpu'] = line.split(':', 1)[1].strip()
                        break
        except Exception as e:
            logger.debug("Failed to read cpuinfo: %s", e)
            info['cpu'] = "Unknown"

        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if "MemTotal" in line:
                        kb = int(line.split()[1])
                        gb = round(kb / 1024 / 1024, 1)
                        info['memory'] = f"{gb} GB"
                        break
        except Exception as e:
            logger.debug("Failed to read meminfo: %s", e)
            info['memory'] = "Unknown"

        try:
            code, out, err = SystemProber.run_command(["hostnamectl", "hostname"])
            info['hostname'] = out.strip() if code == 0 else "Unknown"
        except Exception as e:
            logger.debug("Failed to run hostnamectl: %s", e)
            info['hostname'] = "Unknown"

        try:
            code, out, err = SystemProber.run_command(["hostnamectl"])
            for line in out.splitlines():
                if "Operating System:" in line:
                    info['os'] = line.split(':', 1)[1].strip()
                elif "Chassis:" in line:
                    chassis = line.split(':', 1)[1].strip()
                    info['chassis'] = chassis.split()[0] if chassis else "desktop"
                elif "Hardware Vendor:" in line:
                    info['vendor'] = line.split(':', 1)[1].strip()
                elif "Hardware Model:" in line:
                    info['model'] = line.split(':', 1)[1].strip()
        except Exception as e:
            logger.debug("Failed to run hostnamectl: %s", e)
            pass

        return info

    @staticmethod
    def has_secure_boot() -> bool:
        paths = [
            "/sys/firmware/efi/vars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c/data",
            "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
        ]

        for path in paths:
            try:
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        data = f.read()
                        if len(data) >= 5:
                            return data[4] == 1
                        elif len(data) >= 1:
                            return data[0] == 1
            except Exception as e:
                logger.debug("SecureBoot detection failed for %s: %s", path, e)
                continue

        return False
