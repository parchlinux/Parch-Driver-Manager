import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile

from parch_driver_manager.system_prober import SystemProber


LSPCI_OUTPUT = """00:02.0 VGA compatible controller [0300]: Intel Corporation Device [8086:a780] (rev 04)
\tSubsystem: Intel Corporation Device [8086:a780]
\tKernel driver in use: i915
\tKernel modules: i915
01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GA106 [GeForce RTX 3060 Lite Hash Rate] [10de:2504] (rev a1)
\tSubsystem: Micro-Star International Co., Ltd. [MSI] Device [1462:3895]
\tKernel driver in use: nvidia
\tKernel modules: nvidia, nouveau, nvidia_drm
00:1f.3 Audio device [0403]: Intel Corporation Device [8086:51ca] (rev 01)
\tSubsystem: Intel Corporation Device [8086:7270]
\tKernel driver in use: snd_hda_intel
\tKernel modules: snd_hda_intel, snd_sof_pci_intel_tgl
00:1f.6 Ethernet controller [0200]: Intel Corporation Ethernet Connection (16) I219-V [8086:1a1f]
\tSubsystem: Intel Corporation Device [8086:7270]
\tKernel driver in use: e1000e
\tKernel modules: e1000e
"""

LSPCI_NVIDIA_ONLY = """01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GA106 [GeForce RTX 3060 Lite Hash Rate] [10de:2504] (rev a1)
\tSubsystem: Micro-Star International Co., Ltd. [MSI] Device [1462:3895]
\tKernel driver in use: nvidia
\tKernel modules: nvidia, nouveau, nvidia_drm
"""

LSUSB_OUTPUT = """Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 001 Device 002: ID 0bda:4853 Realtek Semiconductor Corp. Bluetooth Radio
"""

LSMOD_OUTPUT = """Module                  Size  Used by
btusb                  65536  0
bluetooth            1048576  1 btusb
i915                 3768320  8
nvidia               12345344  101
e1000e                 245760  0
snd_hda_intel           49152  3
"""

RFKILL_OUTPUT = """0: ideapad_bluetooth: Bluetooth
\tSoft blocked: no
\tHard blocked: no
1: phy0: Wireless LAN
\tSoft blocked: no
\tHard blocked: no
"""

SYSTEMCTL_OUTPUT = "active\n"

HOSTNAMECTL_OUTPUT = """myhost
"""

HOSTNAMECTL_INFO_OUTPUT = """   Static hostname: myhost
   Operating System: Arch Linux
       Kernel: Linux 6.12.0-arch1-1
 Hardware Vendor: Intel Corporation
  Hardware Model: Test Model
         Chassis: laptop
"""


class TestSystemProber(unittest.TestCase):

    def setUp(self):
        SystemProber.clear_lspci_cache()
        SystemProber._hw_cache = None

    @patch.object(SystemProber, "run_command")
    def test_get_gpu_info_nvidia(self, mock_run):
        mock_run.return_value = (0, LSPCI_NVIDIA_ONLY, "")

        info = SystemProber.get_gpu_info()
        self.assertEqual(info["vendor"], "NVIDIA")

    @patch.object(SystemProber, "run_command")
    def test_get_gpu_info_intel(self, mock_run):
        intel_only = LSPCI_OUTPUT.split("\n01:00")[0]
        mock_run.return_value = (0, intel_only, "")

        info = SystemProber.get_gpu_info()
        self.assertEqual(info["vendor"], "Intel")

    @patch.object(SystemProber, "run_command")
    def test_get_hardware_devices_parses_lspci(self, mock_run):
        mock_run.return_value = (0, LSPCI_OUTPUT, "")

        devices = SystemProber.get_hardware_devices()
        cats = {d["category"] for d in devices}
        self.assertIn("GPU", cats)
        self.assertIn("Audio", cats)
        self.assertIn("Network", cats)

        gpus = [d for d in devices if d["category"] == "GPU"]
        nvidia = [d for d in gpus if "nvidia" in d["driver"].lower()]
        self.assertEqual(len(nvidia), 1)

    @patch.object(SystemProber, "run_command")
    def test_hybrid_graphics_detection(self, mock_run):
        mock_run.return_value = (0, LSPCI_OUTPUT, "")

        hybrid = SystemProber.is_hybrid_graphics()
        self.assertTrue(hybrid)

    def test_get_session_type_from_env(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=True):
            self.assertEqual(SystemProber.get_session_type(), "wayland")

        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}, clear=True):
            self.assertEqual(SystemProber.get_session_type(), "x11")

    @patch.object(SystemProber, "run_command")
    def test_has_secure_boot_enabled(self, mock_run):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\x00\x00\x00\x00\x01")
            path = f.name

        with patch(
            "parch_driver_manager.system_prober.SystemProber.has_secure_boot",
            return_value=True,
        ):
            self.assertTrue(SystemProber.has_secure_boot())

    def test_get_kernel_info(self):
        with patch.object(SystemProber, "run_command") as mock_run:
            mock_run.return_value = (0, "6.12.0-arch1-1\n", "")
            info = SystemProber.get_kernel_info()
            self.assertEqual(info["version"], "6.12.0-arch1-1")
            self.assertEqual(info["flavor"], "default")

            mock_run.return_value = (0, "6.12.0-arch1-1-lts\n", "")
            info = SystemProber.get_kernel_info()
            self.assertEqual(info["flavor"], "lts")

            mock_run.return_value = (0, "6.12.0-arch1-1-zen\n", "")
            info = SystemProber.get_kernel_info()
            self.assertEqual(info["flavor"], "zen")

    def test_kernel_flavor_detection(self):
        cases = [
            ("6.12.0-arch1-1", "default"),
            ("6.12.0-arch1-1-lts", "lts"),
            ("6.12.0-arch1-1-zen", "zen"),
            ("6.12.0-arch1-1-hardened", "hardened"),
        ]
        for version, expected in cases:
            with self.subTest(version=version):
                with patch.object(SystemProber, "run_command") as mock_run:
                    mock_run.return_value = (0, f"{version}\n", "")
                    info = SystemProber.get_kernel_info()
                    self.assertEqual(info["flavor"], expected)


class TestSystemProberBluetooth(unittest.TestCase):

    def setUp(self):
        SystemProber.clear_lspci_cache()
        SystemProber._hw_cache = None

    @patch.object(SystemProber, "run_command")
    def test_usb_bluetooth_detection(self, mock_run):
        def side_effect(cmd, check=False):
            cmd_str = " ".join(cmd)
            if cmd_str == "lsusb":
                return (0, LSUSB_OUTPUT, "")
            if cmd_str == "lsmod":
                return (0, LSMOD_OUTPUT, "")
            if cmd_str == "rfkill list":
                return (0, RFKILL_OUTPUT, "")
            if cmd_str == "systemctl is-active bluetooth":
                return (0, SYSTEMCTL_OUTPUT, "")
            if cmd_str.startswith("lspci"):
                return (0, LSPCI_OUTPUT, "")
            return (0, "", "")
        mock_run.side_effect = side_effect

        devices = SystemProber.get_hardware_devices()
        bts = [d for d in devices if d["category"] == "Bluetooth"]
        self.assertEqual(len(bts), 1)
        self.assertEqual(bts[0]["driver"], "btusb")

    def test_has_bluetooth_adapter_via_sysfs(self):
        with patch("os.path.isdir", return_value=True), patch(
            "os.listdir", return_value=["hci0"]
        ):
            self.assertTrue(SystemProber.has_bluetooth_adapter())

        with patch("os.path.isdir", return_value=True), patch(
            "os.listdir", return_value=[]
        ):
            self.assertFalse(SystemProber.has_bluetooth_adapter())

        with patch("os.path.isdir", return_value=False):
            self.assertFalse(SystemProber.has_bluetooth_adapter())

    @patch.object(SystemProber, "run_command")
    def test_bluetooth_rfkill_unblocked(self, mock_run):
        mock_run.return_value = (0, RFKILL_OUTPUT, "")
        status = SystemProber.get_bluetooth_rfkill_status()
        self.assertEqual(status, "unblocked")

    @patch.object(SystemProber, "run_command")
    def test_bluetooth_service_running(self, mock_run):
        mock_run.return_value = (0, SYSTEMCTL_OUTPUT, "")
        self.assertTrue(SystemProber.is_bluetooth_service_running())

    @patch.object(SystemProber, "run_command")
    def test_bluetooth_service_not_running(self, mock_run):
        mock_run.return_value = (1, "inactive\n", "")
        self.assertFalse(SystemProber.is_bluetooth_service_running())


class TestSystemProberCache(unittest.TestCase):

    def setUp(self):
        SystemProber.clear_lspci_cache()
        SystemProber._hw_cache = None

    def _mock_subcmds(self, cmd, check=False):
        cmd_str = " ".join(cmd)
        if cmd_str.startswith("lspci"):
            return (0, LSPCI_OUTPUT, "")
        if cmd_str == "lsusb":
            return (0, "", "")
        if cmd_str == "lsmod":
            return (0, "", "")
        if cmd_str == "rfkill list":
            return (0, "", "")
        if cmd_str == "systemctl is-active bluetooth":
            return (0, "inactive\n", "")
        return (0, "", "")

    @patch.object(SystemProber, "run_command")
    def test_get_hardware_devices_caching(self, mock_run):
        mock_run.side_effect = self._mock_subcmds

        devices1 = SystemProber.get_hardware_devices()
        first_count = mock_run.call_count
        devices2 = SystemProber.get_hardware_devices()
        self.assertEqual(len(devices1), len(devices2))
        self.assertGreater(first_count, 0)
        self.assertEqual(mock_run.call_count, first_count)

    def test_clear_lspci_cache_clears_hw_cache(self):
        SystemProber._hw_cache = [{"test": "data"}]
        SystemProber.clear_lspci_cache()
        self.assertIsNone(SystemProber._hw_cache)

    @patch.object(SystemProber, "run_command")
    def test_get_hardware_devices_force(self, mock_run):
        mock_run.side_effect = self._mock_subcmds
        SystemProber.get_hardware_devices()
        first_count = mock_run.call_count
        SystemProber.get_hardware_devices(force=True)
        second_count = mock_run.call_count
        self.assertGreater(second_count, first_count)


if __name__ == "__main__":
    unittest.main()
