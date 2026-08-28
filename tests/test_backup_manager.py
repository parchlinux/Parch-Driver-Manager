import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from parch_driver_manager.backend import BackendRunner
from parch_driver_manager.backup_manager import BackupManager
from parch_driver_manager.system_prober import SystemProber


class TestBackupManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_backup_dir = BackupManager.BACKUP_DIR
        BackupManager.BACKUP_DIR = self.temp_dir
        self.backend = MagicMock(spec=BackendRunner)

    def tearDown(self):
        BackupManager.BACKUP_DIR = self.orig_backup_dir
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_ensure_backup_dir(self):
        custom_dir = os.path.join(self.temp_dir, "custom_backups")
        BackupManager.BACKUP_DIR = custom_dir
        BackupManager._ensure_backup_dir()
        self.assertTrue(os.path.isdir(custom_dir))

    @patch.object(SystemProber, "run_command")
    @patch.object(SystemProber, "get_hardware_devices")
    @patch.object(SystemProber, "get_kernel_info")
    @patch.object(SystemProber, "get_system_info")
    def test_create_backup_success(
        self, mock_sys_info, mock_kernel_info, mock_hw, mock_run_cmd
    ):
        mock_run_cmd.side_effect = [
            (0, "pipewire\nbluez\n", ""),  # pacman -Qq
            (0, "btusb 65536 0\n", ""),     # lsmod
        ]
        mock_hw.return_value = [{"name": "Test GPU", "category": "GPU"}]
        mock_kernel_info.return_value = {"version": "6.12.0", "flavor": "default"}
        mock_sys_info.return_value = {"cpu": "Test CPU", "os": "Parch GNU/Linux"}

        success, backup_path = BackupManager.create_backup(self.backend)
        self.assertTrue(success)
        self.assertTrue(os.path.isdir(backup_path))
        self.assertTrue(os.path.exists(os.path.join(backup_path, "pkglist.txt")))
        self.assertTrue(os.path.exists(os.path.join(backup_path, "modules.txt")))
        self.assertTrue(os.path.exists(os.path.join(backup_path, "hardware.json")))
        self.assertTrue(os.path.exists(os.path.join(backup_path, "metadata.json")))

        with open(os.path.join(backup_path, "metadata.json"), "r") as f:
            meta = json.load(f)
            self.assertEqual(meta["kernel"]["version"], "6.12.0")
            self.assertEqual(meta["driver_count"], 2)

    def test_restore_backup_missing_pkglist(self):
        empty_backup = os.path.join(self.temp_dir, "parch-driver-backup-20260101-000000")
        os.makedirs(empty_backup, exist_ok=True)
        success, msg = BackupManager.restore_backup(self.backend, empty_backup)
        self.assertFalse(success)
        self.assertIn("pkglist.txt Not Found", msg)

    def test_restore_backup_empty_pkglist(self):
        backup_dir = os.path.join(self.temp_dir, "parch-driver-backup-20260101-000000")
        os.makedirs(backup_dir, exist_ok=True)
        with open(os.path.join(backup_dir, "pkglist.txt"), "w") as f:
            f.write("\n\n")

        success, msg = BackupManager.restore_backup(self.backend, backup_dir)
        self.assertTrue(success)
        self.backend.run.assert_not_called()

    def test_restore_backup_success(self):
        backup_dir = os.path.join(self.temp_dir, "parch-driver-backup-20260101-000000")
        os.makedirs(backup_dir, exist_ok=True)
        with open(os.path.join(backup_dir, "pkglist.txt"), "w") as f:
            f.write("pipewire\nbluez\n")

        self.backend.run.return_value = (0, "", "")
        success, msg = BackupManager.restore_backup(self.backend, backup_dir)
        self.assertTrue(success)
        self.backend.run.assert_called_once_with(
            ["pacman", "-S", "--needed", "--noconfirm", "pipewire", "bluez"],
            check=True,
        )

    def test_list_backups_sorted(self):
        b1 = os.path.join(self.temp_dir, "parch-driver-backup-20260101-100000")
        b2 = os.path.join(self.temp_dir, "parch-driver-backup-20260102-120000")
        os.makedirs(b1, exist_ok=True)
        os.makedirs(b2, exist_ok=True)

        with open(os.path.join(b1, "metadata.json"), "w") as f:
            json.dump({"date": "20260101-100000", "driver_count": 3}, f)
        with open(os.path.join(b2, "metadata.json"), "w") as f:
            json.dump({"date": "20260102-120000", "driver_count": 5}, f)

        backups = BackupManager.list_backups()
        self.assertEqual(len(backups), 2)
        self.assertEqual(backups[0]["name"], "parch-driver-backup-20260102-120000")
        self.assertEqual(backups[1]["name"], "parch-driver-backup-20260101-100000")

    def test_delete_backup(self):
        b1 = os.path.join(self.temp_dir, "parch-driver-backup-20260101-100000")
        os.makedirs(b1, exist_ok=True)

        success, msg = BackupManager.delete_backup(b1)
        self.assertTrue(success)
        self.assertFalse(os.path.exists(b1))

        success, msg = BackupManager.delete_backup(b1)
        self.assertFalse(success)

    def test_dir_size_formatting(self):
        test_dir = os.path.join(self.temp_dir, "size_test")
        os.makedirs(test_dir, exist_ok=True)
        with open(os.path.join(test_dir, "file.bin"), "wb") as f:
            f.write(b"x" * 2048)

        formatted = BackupManager._get_dir_size(test_dir)
        self.assertEqual(formatted, "2.0 KB")


if __name__ == "__main__":
    unittest.main()
