import unittest
from unittest.mock import patch, MagicMock

from parch_driver_manager.manager import DriverManager
from parch_driver_manager.profiles import DriverProfile
from parch_driver_manager.system_prober import SystemProber


class TestDriverManager(unittest.TestCase):

    def setUp(self):
        self.backend = MagicMock()
        self.manager = DriverManager(self.backend)

    def test_initialization(self):
        self.assertEqual(self.manager.backend, self.backend)

    @patch.object(SystemProber, "run_command")
    def test_is_package_installed(self, mock_run):
        mock_run.return_value = (0, "", "")
        self.assertTrue(self.manager.is_package_installed("test-pkg"))

        mock_run.return_value = (1, "", "")
        self.assertFalse(self.manager.is_package_installed("missing-pkg"))

    @patch.object(SystemProber, "run_command")
    def test_get_installed_packages(self, mock_run):
        mock_run.return_value = (0, "pkg1\npkg2\npkg3\n", "")
        packages = self.manager.get_installed_packages()
        self.assertEqual(packages, ["pkg1", "pkg2", "pkg3"])

        mock_run.return_value = (1, "", "")
        packages = self.manager.get_installed_packages()
        self.assertEqual(packages, [])

    @patch.object(DriverManager, "is_package_installed")
    def test_install_profile_all_already_installed(self, mock_is_installed):
        mock_is_installed.return_value = True
        profile = DriverProfile(
            name="Test",
            description="Test profile",
            packages=["pkg1", "pkg2"],
            category="GPU",
        )
        self.manager.install_profile(profile)
        self.backend.run.assert_not_called()

    @patch.object(DriverManager, "is_package_installed")
    def test_install_profile_some_not_installed(self, mock_is_installed):
        call_count = {"count": 0}

        def side_effect(pkg):
            call_count["count"] += 1
            return pkg == "pkg1"
        mock_is_installed.side_effect = side_effect

        profile = DriverProfile(
            name="Test",
            description="Test profile",
            packages=["pkg1", "pkg2"],
            category="GPU",
        )
        self.manager.install_profile(profile)
        self.backend.run.assert_called_once()
        args = self.backend.run.call_args[0][0]
        self.assertIn("pkg2", args)
        self.assertNotIn("pkg1", args)

    @patch.object(DriverManager, "is_package_installed")
    def test_remove_profile_with_post_remove(self, mock_is_installed):
        mock_is_installed.return_value = True
        post_remove_called = [False]

        def post_remove(runner):
            post_remove_called[0] = True

        profile = DriverProfile(
            name="Test",
            description="Test profile",
            packages=["pkg1"],
            category="GPU",
            post_remove=post_remove,
        )
        self.manager.remove_profile(profile)
        self.backend.run.assert_called_once()
        self.assertTrue(post_remove_called[0])

    @patch.object(DriverManager, "is_package_installed")
    def test_remove_profile_none_installed(self, mock_is_installed):
        mock_is_installed.return_value = False
        profile = DriverProfile(
            name="Test",
            description="Test profile",
            packages=["pkg1"],
            category="GPU",
        )
        self.manager.remove_profile(profile)
        self.backend.run.assert_not_called()

    @patch.object(DriverManager, "is_package_installed")
    def test_disable_driver_with_module(self, mock_is_installed):
        self.backend.disable_hardware.return_value = (0, "", "")
        profile = DriverProfile(
            name="Test",
            description="Test profile",
            packages=["pkg1"],
            category="GPU",
            module="nvidia",
        )
        self.manager.disable_driver(profile)
        self.backend.disable_hardware.assert_called_once_with("nvidia")

    def test_disable_driver_no_module(self):
        profile = DriverProfile(
            name="Test",
            description="Test profile",
            packages=["pkg1"],
            category="GPU",
        )
        self.manager.disable_driver(profile)
        self.backend.disable_hardware.assert_not_called()

    @patch.object(DriverManager, "is_package_installed")
    def test_enable_driver_with_module(self, mock_is_installed):
        self.backend.enable_hardware.return_value = (0, "", "")
        profile = DriverProfile(
            name="Test",
            description="Test profile",
            packages=["pkg1"],
            category="GPU",
            module="nvidia",
        )
        self.manager.enable_driver(profile)
        self.backend.enable_hardware.assert_called_once_with("nvidia")

    def test_enable_driver_no_module(self):
        profile = DriverProfile(
            name="Test",
            description="Test profile",
            packages=["pkg1"],
            category="GPU",
        )
        self.manager.enable_driver(profile)
        self.backend.enable_hardware.assert_not_called()


if __name__ == "__main__":
    unittest.main()
