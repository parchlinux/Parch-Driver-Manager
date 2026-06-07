import subprocess
import os
from typing import List, Dict, Any, Tuple

class CommandError(Exception):
    def __init__(self, cmd: List[str], returncode: int, stdout: str, stderr: str):
        super().__init__(f"Command failed: {' '.join(cmd)} (code {returncode})")
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def debug_log(msg: str) -> None:
    print(f"[ParchDM] {msg}")

class SystemProber:
    @staticmethod
    def run_command(command: List[str], check: bool = False) -> Tuple[int, str, str]:
        debug_log(f"Running command: {' '.join(command)}")
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
    def get_lspci() -> str:
        code, out, err = SystemProber.run_command(["lspci", "-nnk"])
        if code != 0:
            debug_log(f"lspci failed: {err.strip()}")
            return ""
        return out

    @staticmethod
    def get_hardware_devices() -> List[Dict[str, Any]]:
        lspci = SystemProber.get_lspci()
        devices = []
        current_dev = {}
        
        for line in lspci.splitlines():
            if not line.startswith('\t') and line.strip():
                if current_dev:
                    devices.append(current_dev)
                
                parts = line.split(': ', 1)
                if len(parts) == 2:
                    current_dev = {
                        'pci': parts[0].split(' ')[0],
                        'name': parts[1],
                        'category': 'Other',
                        'driver': None,
                        'modules': []
                    }
                    lower = line.lower()
                    if 'vga' in lower or '3d' in lower or 'display' in lower:
                        current_dev['category'] = 'GPU'
                    elif 'network' in lower or 'ethernet' in lower:
                        current_dev['category'] = 'Network'
                    elif 'audio' in lower:
                        current_dev['category'] = 'Audio'
                    elif 'bluetooth' in lower:
                        current_dev['category'] = 'Bluetooth'
                    elif 'usb' in lower or 'serial' in lower:
                        current_dev['category'] = 'Other'
            else:
                line = line.strip()
                if line.startswith('Kernel driver in use:'):
                    current_dev['driver'] = line.split(': ')[1]
                elif line.startswith('Kernel modules:'):
                    current_dev['modules'] = [m.strip() for m in line.split(': ')[1].split(',')]
        
        if current_dev:
            devices.append(current_dev)
            
        return devices

    @staticmethod
    def get_gpu_info() -> Dict[str, Any]:
        lspci = SystemProber.get_lspci()
        vendor = "Unknown"

        for line in lspci.splitlines():
            lower = line.lower()
            if "vga compatible controller" in lower or "3d controller" in lower:
                if "nvidia" in lower:
                    vendor = "NVIDIA"
                elif "amd" in lower or "advanced micro devices" in lower or "ati" in lower:
                    vendor = "AMD"
                elif "intel" in lower:
                    vendor = "Intel"
                break

        return {"vendor": vendor, "raw": lspci}

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
        lspci = SystemProber.get_lspci().lower()
        has_intel = "intel corporation" in lspci
        has_nvidia = "nvidia corporation" in lspci
        has_amd = "advanced micro devices" in lspci or "amd" in lspci
        return has_intel and (has_nvidia or has_amd)

    @staticmethod
    def has_secure_boot() -> bool:
        try:
            path = "/sys/firmware/efi/vars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c/data"
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = f.read(1)
                    return data == b"\x01"
        except Exception as e:
            debug_log(f"SecureBoot detection failed: {e}")
        return False
