import unittest

from parch_driver_manager.profiles import DriverProfile, DriverProfiles


class TestDriverProfile(unittest.TestCase):

    def test_create_profile(self):
        profile = DriverProfile(
            name="Test Driver",
            description="A test driver profile",
            packages=["test-pkg"],
            category="GPU",
            module="test_mod",
        )
        self.assertEqual(profile.name, "Test Driver")
        self.assertEqual(profile.description, "A test driver profile")
        self.assertEqual(profile.packages, ["test-pkg"])
        self.assertEqual(profile.category, "GPU")
        self.assertEqual(profile.module, "test_mod")

    def test_profile_without_module(self):
        profile = DriverProfile(
            name="No Module",
            description="Profile without a module",
            packages=["pkg1"],
            category="Network",
        )
        self.assertIsNone(profile.module)
        self.assertIsNone(profile.post_install)
        self.assertIsNone(profile.post_remove)

    def test_profile_with_callbacks(self):
        def dummy_cb(runner):
            pass

        profile = DriverProfile(
            name="With Callbacks",
            description="Has callbacks",
            packages=["pkg1"],
            category="Audio",
            module="audio_mod",
            post_install=dummy_cb,
            post_remove=dummy_cb,
        )
        self.assertIsNotNone(profile.post_install)
        self.assertIsNotNone(profile.post_remove)


class TestDriverProfiles(unittest.TestCase):

    def test_nvidia_profiles_default(self):
        profiles = DriverProfiles.get_nvidia_profiles("default")
        self.assertEqual(len(profiles), 2)
        self.assertEqual(profiles[0].category, "GPU")
        self.assertIn("nvidia-dkms", profiles[0].packages)
        self.assertEqual(profiles[0].module, "nvidia")
        self.assertEqual(profiles[1].module, "nouveau")

    def test_nvidia_profiles_lts(self):
        profiles = DriverProfiles.get_nvidia_profiles("lts")
        self.assertEqual(len(profiles), 2)
        self.assertIn("linux-lts", profiles[0].packages)

    def test_nvidia_profiles_zen(self):
        profiles = DriverProfiles.get_nvidia_profiles("zen")
        self.assertIn("linux-zen", profiles[0].packages)

    def test_amd_profiles(self):
        profiles = DriverProfiles.get_amd_profiles("default")
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].module, "amdgpu")
        self.assertIn("mesa", profiles[0].packages)

    def test_intel_profiles(self):
        profiles = DriverProfiles.get_intel_profiles("default")
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].module, "i915")

    def test_gpu_profiles_nvidia(self):
        profiles = DriverProfiles.get_gpu_profiles("NVIDIA", "default")
        self.assertEqual(len(profiles), 2)
        self.assertEqual(profiles[0].name[:6], "NVIDIA")

    def test_gpu_profiles_amd(self):
        profiles = DriverProfiles.get_gpu_profiles("AMD", "default")
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].name, "AMD Open Source")

    def test_gpu_profiles_intel(self):
        profiles = DriverProfiles.get_gpu_profiles("INTEL", "default")
        self.assertEqual(len(profiles), 1)

    def test_gpu_profiles_unknown(self):
        profiles = DriverProfiles.get_gpu_profiles("Unknown", "default")
        self.assertEqual(len(profiles), 0)

    def test_network_profiles(self):
        profiles = DriverProfiles.get_network_profiles()
        self.assertGreater(len(profiles), 0)
        for p in profiles:
            self.assertEqual(p.category, "Network")

    def test_bluetooth_profiles(self):
        profiles = DriverProfiles.get_bluetooth_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].category, "Bluetooth")
        self.assertIn("bluez", profiles[0].packages)

    def test_audio_profiles(self):
        profiles = DriverProfiles.get_audio_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].category, "Audio")
        self.assertIn("pipewire", profiles[0].packages)

    def test_get_all_profiles_nvidia(self):
        profiles = DriverProfiles.get_all_profiles("NVIDIA", "default")
        self.assertGreater(len(profiles), 3)

    def test_get_all_profiles_unknown(self):
        profiles = DriverProfiles.get_all_profiles("Unknown", "default")
        self.assertGreater(len(profiles), 3)


if __name__ == "__main__":
    unittest.main()
