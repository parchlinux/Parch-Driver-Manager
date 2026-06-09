import logging
import os

_log_path = os.path.expanduser("~/.local/share/parch-driver-manager/operations.log")
os.makedirs(os.path.dirname(_log_path), exist_ok=True)
logging.basicConfig(filename=_log_path, level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s')

from typing import List, Callable, Optional
from system_prober import SystemProber
from backend import BackendRunner
from profiles import DriverProfile

class DriverManager:
    def __init__(self, backend: BackendRunner):
        self.backend = backend

    def get_installed_packages(self) -> List[str]:
        code, out, err = SystemProber.run_command(["pacman", "-Qq"])
        if code != 0:
            return []
        return out.splitlines()

    def get_installed_packages(self) -> List[str]:
        code, out, err = SystemProber.run_command(["pacman", "-Qq"])
        if code != 0:
            return []
        return out.splitlines()

    def is_package_installed(self, pkg: str) -> bool:
        code, _, _ = SystemProber.run_command(["pacman", "-Qq", pkg])
        return code == 0

    def install_profile(self, profile: DriverProfile, progress_cb: Optional[Callable[[str], None]] = None):
        installed = self.get_installed_packages_set()
        pkgs_to_install = [p for p in profile.packages if p not in installed]
        if not pkgs_to_install:
            if progress_cb: progress_cb("All packages in this profile are already installed.")
            return

        if progress_cb: progress_cb(f"Installing: {' '.join(pkgs_to_install)}")
        logging.info(f"Installing packages: {pkgs_to_install}")
        self.backend.run(["pacman", "-S", "--needed", "--noconfirm"] + pkgs_to_install, check=True)

        if profile.post_install:
            if progress_cb: progress_cb("Running post-install steps…")
            profile.post_install(self.backend)

    def remove_profile(self, profile: DriverProfile, progress_cb: Optional[Callable[[str], None]] = None):
        installed = self.get_installed_packages_set()
        pkgs_to_remove = [p for p in profile.packages if p in installed]
        if not pkgs_to_remove:
            if progress_cb: progress_cb("None of the packages in this profile are installed.")
            return

        if progress_cb: progress_cb(f"Removing: {' '.join(pkgs_to_remove)}")
        logging.info(f"Removing packages: {pkgs_to_remove}")
        self.backend.run(["pacman", "-Rns", "--noconfirm"] + pkgs_to_remove, check=True)

        if profile.post_remove:
            if progress_cb: progress_cb("Running post-remove steps…")
            profile.post_remove(self.backend)

    def disable_driver(self, profile: DriverProfile, progress_cb: Optional[Callable[[str], None]] = None):
        if not profile.module:
            if progress_cb: progress_cb("No kernel module defined for this profile to disable.")
            return
        if progress_cb: progress_cb(f"Disabling module: {profile.module}")
        code, out, err = self.backend.disable_hardware(profile.module)
        if code == 0:
            if progress_cb: progress_cb(f"Module {profile.module} disabled successfully.")
        else:
            if progress_cb: progress_cb(f"Failed to disable module: {err}")

    def enable_driver(self, profile: DriverProfile, progress_cb: Optional[Callable[[str], None]] = None):
        if not profile.module:
            if progress_cb: progress_cb("No kernel module defined for this profile to enable.")
            return
        if progress_cb: progress_cb(f"Enabling module: {profile.module}")
        code, out, err = self.backend.enable_hardware(profile.module)
        if code == 0:
            if progress_cb: progress_cb(f"Module {profile.module} enabled successfully.")
        else:
            if progress_cb: progress_cb(f"Failed to enable module: {err}")
