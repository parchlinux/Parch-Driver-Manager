import logging
from typing import List, Callable, Optional
import shlex

from .backend import BackendRunner

logger = logging.getLogger(__name__)


class DriverProfile:
    def __init__(
        self,
        name: str,
        description: str,
        packages: List[str],
        category: str,
        module: Optional[str] = None,
        post_install: Optional[Callable[['BackendRunner'], None]] = None,
        post_remove: Optional[Callable[['BackendRunner'], None]] = None,
    ):
        self.name = name
        self.description = description
        self.packages = packages
        self.category = category
        self.module = module
        self.post_install = post_install
        self.post_remove = post_remove


class DriverProfiles:
    @staticmethod
    def get_nvidia_profiles(kernel_flavor: str) -> List[DriverProfile]:
        open_dkms = "nvidia-open-dkms"
        utils = "nvidia-utils"
        settings = "nvidia-settings"

        def post_install_nvidia(runner: BackendRunner):
            logger.debug("Running NVIDIA post-install steps")
            blacklist_path = "/etc/modprobe.d/blacklist-nouveau.conf"
            content = "blacklist nouveau\noptions nouveau modeset=0\n"
            runner.write_file(blacklist_path, content)
            runner.run(["mkinitcpio", "-P"], check=True)

        def post_remove_nvidia(runner: BackendRunner):
            logger.debug("Running NVIDIA post-remove steps")
            blacklist_path = "/etc/modprobe.d/blacklist-nouveau.conf"
            runner.run(["rm", "-f", blacklist_path], check=False)
            runner.run(["mkinitcpio", "-P"], check=False)

        return [
            DriverProfile(
                name="NVIDIA Open Kernel Modules",
                description="Open-source NVIDIA GPU driver (nvidia-open)",
                packages=[open_dkms, utils, settings],
                category="GPU",
                module="nvidia",
                post_install=post_install_nvidia,
                post_remove=post_remove_nvidia,
            )
        ]

    @staticmethod
    def get_amd_profiles(kernel_flavor: str) -> List[DriverProfile]:
        return [
            DriverProfile(
                name="AMD Open Source",
                description="Open-source AMDGPU stack (Mesa, xf86-video-amdgpu, Vulkan)",
                packages=["mesa", "xf86-video-amdgpu", "vulkan-radeon"],
                category="GPU",
                module="amdgpu"
            )
        ]

    @staticmethod
    def get_intel_profiles(kernel_flavor: str) -> List[DriverProfile]:
        return [
            DriverProfile(
                name="Intel Open Source",
                description="Open-source Intel graphics stack (Mesa, xf86-video-intel, Vulkan)",
                packages=["mesa", "xf86-video-intel", "vulkan-intel"],
                category="GPU",
                module="i915"
            )
        ]

    @staticmethod
    def get_gpu_profiles(vendor: Any, kernel_flavor: str) -> List[DriverProfile]:
        vendors = []
        if isinstance(vendor, list):
            vendors = vendor
        elif isinstance(vendor, str):
            vendors = [v.strip() for v in vendor.split(",") if v.strip()]

        profiles: List[DriverProfile] = []
        seen_names = set()

        for v in vendors:
            v_upper = v.upper()
            v_profiles = []
            if v_upper == "NVIDIA":
                v_profiles = DriverProfiles.get_nvidia_profiles(kernel_flavor)
            elif v_upper == "AMD":
                v_profiles = DriverProfiles.get_amd_profiles(kernel_flavor)
            elif v_upper == "INTEL":
                v_profiles = DriverProfiles.get_intel_profiles(kernel_flavor)

            for p in v_profiles:
                if p.name not in seen_names:
                    seen_names.add(p.name)
                    profiles.append(p)

        return profiles

    @staticmethod
    def get_network_profiles() -> List[DriverProfile]:
        return [
            DriverProfile(
                name="NetworkManager",
                description="NetworkManager, nm-connection-editor and basic networking tools",
                packages=["networkmanager", "nm-connection-editor"],
                category="Network",
            ),
            DriverProfile(
                name="iwd + NetworkManager",
                description="NetworkManager with iwd backend for Wi-Fi",
                packages=["networkmanager", "iwd"],
                category="Network",
            ),
            DriverProfile(
                name="Broadcom Wi-Fi (broadcom-wl)",
                description="Broadcom proprietary Wi-Fi driver via DKMS",
                packages=["broadcom-wl-dkms"],
                category="Network",
                module="wl",
            ),
            DriverProfile(
                name="RTL8821CE Wi-Fi",
                description="Realtek RTL8821CE driver (common in laptops)",
                packages=["rtl8821ce-dkms-git"],
                category="Network",
                module="8821ce",
            ),
        ]

    @staticmethod
    def get_bluetooth_profiles() -> List[DriverProfile]:
        def post_install_bluetooth(runner: BackendRunner):
            logger.debug("Enabling bluetooth.service")
            runner.run(["systemctl", "enable", "--now", "bluetooth.service"], check=False)

        def post_remove_bluetooth(runner: BackendRunner):
            logger.debug("Disabling bluetooth.service")
            runner.run(["systemctl", "disable", "--now", "bluetooth.service"], check=False)

        return [
            DriverProfile(
                name="Parch Bluetooth Stack",
                description="Parch Linux Bluetooth meta-package with BlueZ and KDE Plasma Bluedevil integration",
                packages=["parch-bluetooth", "bluez", "bluez-utils", "bluedevil"],
                category="Bluetooth",
                module="btusb",
                post_install=post_install_bluetooth,
                post_remove=post_remove_bluetooth,
            ),
            DriverProfile(
                name="BlueZ + KDE Bluedevil",
                description="Standard Bluetooth stack with KDE Plasma Bluedevil panel integration",
                packages=["bluez", "bluez-utils", "bluedevil"],
                category="Bluetooth",
                module="btusb",
                post_install=post_install_bluetooth,
                post_remove=post_remove_bluetooth,
            ),
            DriverProfile(
                name="BlueZ + Blueman",
                description="Standard Bluetooth stack with GTK Blueman GUI",
                packages=["bluez", "bluez-utils", "blueman"],
                category="Bluetooth",
                module="btusb",
                post_install=post_install_bluetooth,
                post_remove=post_remove_bluetooth,
            ),
        ]

    @staticmethod
    def get_audio_profiles() -> List[DriverProfile]:
        return [
            DriverProfile(
                name="PipeWire Audio",
                description="PipeWire audio stack with ALSA and PulseAudio compatibility",
                packages=[
                    "pipewire",
                    "pipewire-alsa",
                    "pipewire-pulse",
                    "wireplumber",
                ],
                category="Audio",
            )
        ]

    @staticmethod
    def get_all_profiles(gpu_vendor: str, kernel_flavor: str) -> List[DriverProfile]:
        profiles: List[DriverProfile] = []
        profiles.extend(DriverProfiles.get_gpu_profiles(gpu_vendor, kernel_flavor))
        profiles.extend(DriverProfiles.get_network_profiles())
        profiles.extend(DriverProfiles.get_bluetooth_profiles())
        profiles.extend(DriverProfiles.get_audio_profiles())
        return profiles
