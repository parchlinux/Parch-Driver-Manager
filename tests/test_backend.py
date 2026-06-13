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
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        bash_script = cmd[2] if len(cmd) > 2 else ""
        self.assertIn("test_mod", bash_script)
        self.assertIn("blacklist", bash_script)
        self.assertIn("modprobe -r", bash_script)

    @patch.object(BackendRunner, "run")
    def test_enable_hardware(self, mock_run):
        mock_run.return_value = (0, "", "")
        code, out, err = self.runner.enable_hardware("test_mod")
        self.assertEqual(code, 0)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        bash_script = cmd[2] if len(cmd) > 2 else ""
        self.assertIn("test_mod", bash_script)
        self.assertIn("modprobe", bash_script)

    @patch("subprocess.Popen")
    def test_run_with_pkexec(self, mock_popen):
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.communicate.return_value = ("output", "")
        mock_popen.return_value = proc_mock

        runner = BackendRunner(use_pkexec=True)
        code, out, err = runner.run(["pacman", "-Q", "test-pkg"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "output")
        call_args = mock_popen.call_args[0][0]
        self.assertEqual(call_args[0], "pkexec")

    @patch("subprocess.Popen")
    def test_run_without_pkexec(self, mock_popen):
        proc_mock = MagicMock()
        proc_mock.returncode = 0
        proc_mock.communicate.return_value = ("output", "")
        mock_popen.return_value = proc_mock

        runner = BackendRunner(use_pkexec=False)
        code, out, err = runner.run(["echo", "hello"])
        self.assertEqual(code, 0)
        call_args = mock_popen.call_args[0][0]
        self.assertNotIn("pkexec", call_args)

    @patch("subprocess.Popen")
    def test_run_with_check_raises_on_failure(self, mock_popen):
        proc_mock = MagicMock()
        proc_mock.returncode = 1
        proc_mock.communicate.return_value = ("", "error")
        mock_popen.return_value = proc_mock

        with self.assertRaises(CommandError):
            self.runner.run(["false"], check=True)

    @patch("subprocess.Popen")
    def test_run_without_check_returns_on_failure(self, mock_popen):
        proc_mock = MagicMock()
        proc_mock.returncode = 1
        proc_mock.communicate.return_value = ("", "error")
        mock_popen.return_value = proc_mock

        code, out, err = self.runner.run(["false"], check=False)
        self.assertEqual(code, 1)

    def test_shlex_quoting_in_disable_hardware(self):
        with patch.object(self.runner, "run") as mock_run:
            mock_run.return_value = (0, "", "")
            self.runner.disable_hardware("nvidia;rm -rf /")
            cmd = mock_run.call_args[0][0]
            self.assertEqual(cmd[0], "bash")
            self.assertEqual(cmd[1], "-c")
            script = cmd[2]
            self.assertIn("nvidia", script)
            quoted = shlex.quote("nvidia;rm -rf /")
            self.assertIn(quoted, script)


class TestCommandError(unittest.TestCase):

    def test_command_error_exception(self):
        exc = CommandError(["test-cmd"], 1, "stdout", "stderr")
        self.assertEqual(exc.returncode, 1)
        self.assertEqual(exc.stdout, "stdout")
        self.assertEqual(exc.stderr, "stderr")
        self.assertIn("test-cmd", str(exc))


if __name__ == "__main__":
    unittest.main()
