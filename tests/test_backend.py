import unittest
from unittest.mock import patch, MagicMock
import shlex
import subprocess

from parch_driver_manager.backend import BackendRunner, CommandError


class TestBackendRunner(unittest.TestCase):

    def setUp(self):
        self.runner = BackendRunner(use_pkexec=False)

    def test_initialization_default_pkexec(self):
        runner = BackendRunner(use_pkexec=True)
        self.assertTrue(runner.use_pkexec)

    def test_initialization_no_pkexec(self):
        runner = BackendRunner(use_pkexec=False)
        self.assertFalse(runner.use_pkexec)

    @patch.object(BackendRunner, "run")
    def test_disable_hardware(self, mock_run):
        mock_run.return_value = (0, "", "")
        code, out, err = self.runner.disable_hardware("test_mod")
        self.assertEqual(code, 0)
        self.assertTrue(mock_run.called)
        calls = [c[0][0] for c in mock_run.call_args_list]
        self.assertIn(['cat', '/etc/modprobe.d/parch-dm-blacklist.conf'], calls)

    @patch.object(BackendRunner, "run")
    def test_enable_hardware(self, mock_run):
        mock_run.return_value = (0, "", "")
        code, out, err = self.runner.enable_hardware("test_mod")
        self.assertEqual(code, 0)
        self.assertTrue(mock_run.called)
        calls = [c[0][0] for c in mock_run.call_args_list]
        self.assertIn(['modprobe', 'test_mod'], calls)

    def test_invalid_module_name_validation(self):
        code, out, err = self.runner.disable_hardware("nvidia;rm -rf /")
        self.assertEqual(code, 1)
        self.assertIn("Invalid module name", err)

        code_en, out_en, err_en = self.runner.enable_hardware("invalid module name!")
        self.assertEqual(code_en, 1)
        self.assertIn("Invalid module name", err_en)


class TestCommandError(unittest.TestCase):

    def test_command_error_exception(self):
        exc = CommandError(["test-cmd"], 1, "stdout", "stderr")
        self.assertEqual(exc.returncode, 1)
        self.assertEqual(exc.stdout, "stdout")
        self.assertEqual(exc.stderr, "stderr")
        self.assertIn("test-cmd", str(exc))


if __name__ == "__main__":
    unittest.main()
