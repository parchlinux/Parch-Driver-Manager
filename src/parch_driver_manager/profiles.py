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
        dkms = "nvidia-dkms"
        utils = "nvidia-utils"
        settings = "nvidia-settings"

        if kernel_flavor == "lts":
            kernel_pkg = "linux-lts"
        elif kernel_flavor == "zen":
            kernel_pkg = "linux-zen"
        elif kernel_flavor == "hardened":
            kernel_pkg = "linux-hardened"
        else:
            kernel_flavor = "default"
            kernel_pkg = "linux"

        def post_install_nvidia(runner: BackendRunner):
            logger.debug("Running NVIDIA post-install steps")
            blacklist_path = "/etc/modprobe.d/blacklist-nouveau.conf"
            content = "blacklist nouveau\noptions nouveau modeset=0\n"
            runner.run(
                ["bash", "-c", f"echo '{content}' > {shlex.quote(blacklist_path)}"],
                check=True,
            )
            runner.run(["mkinitcpio", "-P"], check=True)

        def post_remove_nvidia(runner: BackendRunner):
            logger.debug("Running NVIDIA post-remove steps")
            blacklist_path = "/etc/modprobe.d/blacklist-nouveau.conf"
            runner.run(["rm", "-f", blacklist_path], check=False)
            runner.run(["mkinitcpio", "-P"], check=False)

        return [
            DriverProfile(
                name=f"NVIDIA ({kernel_flavor})",
                description=f"Proprietary NVIDIA driver for {kernel_pkg}",
                packages=[kernel_pkg, dkms, utils, settings],
                category="GPU",
                module="nvidia",
                post_install=post_install_nvidia,
                post_remove=post_remove_nvidia,
            ),
            DriverProfile(
                name="NVIDIA Open Source (Nouveau)",
                description="Open-source Nouveau driver for NVIDIA cards",
                packages=["mesa", "xf86-video-nouveau"],
                category="GPU",
                module="nouveau",
            ),
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
    def get_gpu_profiles(vendor: str, kernel_flavor: str) -> List[DriverProfile]:
        vendor = vendor.upper()
        if vendor == "NVIDIA":
            return DriverProfiles.get_nvidia_profiles(kernel_flavor)
        if vendor == "AMD":
            return DriverProfiles.get_amd_profiles(kernel_flavor)
        if vendor == "INTEL":
            return DriverProfiles.get_intel_profiles(kernel_flavor)
        return []

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
        return [
            DriverProfile(
                name="BlueZ + Blueman",
                description="Bluetooth stack with BlueZ and Blueman GUI",
                packages=["bluez", "bluez-utils", "blueman"],
                category="Bluetooth",
                module="btusb"
            )
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
