import datetime
import json
import logging
import os
import shutil
from typing import Any, Dict, List, Tuple

from .backend import BackendRunner
from .profiles import DriverProfiles
from .system_prober import SystemProber

logger = logging.getLogger(__name__)


class BackupManager:
    BACKUP_DIR = os.path.expanduser("~/ParchDriverBackups")

    @staticmethod
    def _ensure_backup_dir() -> None:
        os.makedirs(BackupManager.BACKUP_DIR, exist_ok=True)

    @staticmethod
    def create_backup(backend: BackendRunner) -> Tuple[bool, str]:
        try:
            BackupManager._ensure_backup_dir()
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = os.path.join(BackupManager.BACKUP_DIR, f"parch-driver-backup-{timestamp}")
            os.makedirs(backup_path, exist_ok=True)

            pkg_list = BackupManager._get_driver_packages()
            with open(os.path.join(backup_path, "pkglist.txt"), "w") as f:
                f.write("\n".join(pkg_list) + ("\n" if pkg_list else ""))

            code, modules_out, _ = SystemProber.run_command(["lsmod"])
            if code == 0:
                with open(os.path.join(backup_path, "modules.txt"), "w") as f:
                    f.write(modules_out)

            hardware = SystemProber.get_hardware_devices()
            with open(os.path.join(backup_path, "hardware.json"), "w") as f:
                json.dump(hardware, f, indent=2, default=str)

            sys_info = {
                "kernel": SystemProber.get_kernel_info(),
                "system": SystemProber.get_system_info(),
                "date": timestamp,
                "driver_count": len(pkg_list),
            }
            with open(os.path.join(backup_path, "metadata.json"), "w") as f:
                json.dump(sys_info, f, indent=2)

            return True, backup_path

        except Exception as e:
            logger.error("Failed to create backup: %s", e, exc_info=True)
            return False, str(e)

    @staticmethod
    def _get_driver_packages() -> List[str]:
        drivers = set()
        all_profiles = DriverProfiles.get_all_profiles("NVIDIA,AMD,INTEL", "default")
        for profile in all_profiles:
            for pkg in profile.packages:
                drivers.add(pkg)

        code, out, _ = SystemProber.run_command(["pacman", "-Qq"])
        if code == 0:
            installed = set(out.splitlines())
            return sorted(list(drivers & installed))
        return sorted(list(drivers))

    @staticmethod
    def restore_backup(backend: BackendRunner, backup_path: str) -> Tuple[bool, str]:
        try:
            pkglist_path = os.path.join(backup_path, "pkglist.txt")
            if not os.path.exists(pkglist_path):
                return False, "pkglist.txt Not Found."

            with open(pkglist_path, "r") as f:
                packages = [line.strip() for line in f.read().splitlines() if line.strip()]

            if not packages:
                return True, "No packages to restore."

            backend.run(["pacman", "-S", "--needed", "--noconfirm"] + packages, check=True)

            return True, f"{len(packages)} Package(s) Installed."

        except Exception as e:
            logger.error("Failed to restore backup from %s: %s", backup_path, e, exc_info=True)
            return False, str(e)

    @staticmethod
    def list_backups() -> List[Dict[str, Any]]:
        BackupManager._ensure_backup_dir()
        backups = []

        if not os.path.exists(BackupManager.BACKUP_DIR):
            return []

        for item in os.listdir(BackupManager.BACKUP_DIR):
            path = os.path.join(BackupManager.BACKUP_DIR, item)
            if os.path.isdir(path) and item.startswith("parch-driver-backup-"):
                metadata: Dict[str, Any] = {}
                meta_path = os.path.join(path, "metadata.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r") as f:
                            metadata = json.load(f)
                    except Exception:
                        pass

                backups.append({
                    "name": item,
                    "path": path,
                    "date": metadata.get("date", item.replace("parch-driver-backup-", "")),
                    "driver_count": metadata.get("driver_count", 0),
                    "size": BackupManager._get_dir_size(path),
                })

        return sorted(backups, key=lambda x: x["date"], reverse=True)

    @staticmethod
    def _get_dir_size(path: str) -> str:
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)

        if total < 1024:
            return f"{total} B"
        elif total < 1024 * 1024:
            return f"{total / 1024:.1f} KB"
        elif total < 1024 * 1024 * 1024:
            return f"{total / (1024 * 1024):.1f} MB"
        else:
            return f"{total / (1024 * 1024 * 1024):.2f} GB"

    @staticmethod
    def delete_backup(backup_path: str) -> Tuple[bool, str]:
        try:
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
                return True, "Backup Deleted"
            return False, "Backup Folder Not Found"
        except Exception as e:
            logger.error("Failed to delete backup %s: %s", backup_path, e, exc_info=True)
            return False, str(e)
