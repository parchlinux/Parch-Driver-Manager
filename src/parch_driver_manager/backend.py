import logging
import re
import subprocess
from typing import List, Tuple

from .system_prober import CommandError

logger = logging.getLogger(__name__)

MODULE_NAME_REGEX = re.compile(r'^[a-zA-Z0-9_\-]+$')


class BackendRunner:
    def __init__(self, use_pkexec: bool = True):
        self.use_pkexec = use_pkexec

    def _build_command(self, cmd: List[str]) -> List[str]:
        if self.use_pkexec:
            return ["pkexec"] + cmd
        return cmd

    def run(self, cmd: List[str], check: bool = True, input_data: str = None) -> Tuple[int, str, str]:
        full_cmd = self._build_command(cmd)
        logger.debug("BackendRunner executing: %s", ' '.join(full_cmd))
        proc = subprocess.Popen(
            full_cmd,
            stdin=subprocess.PIPE if input_data is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = proc.communicate(input=input_data)
        if check and proc.returncode != 0:
            raise CommandError(full_cmd, proc.returncode, out, err)
        return proc.returncode, out, err

    def write_file(self, path: str, content: str) -> Tuple[int, str, str]:
        return self.run(["tee", path], check=True, input_data=content)

    def disable_hardware(self, module: str) -> Tuple[int, str, str]:
        if not MODULE_NAME_REGEX.match(module):
            return 1, "", f"Invalid module name: {module}"

        blacklist_path = "/etc/modprobe.d/parch-dm-blacklist.conf"
        code, out, _ = self.run(["cat", blacklist_path], check=False)
        lines = out.splitlines() if code == 0 else []
        target_line = f"blacklist {module}"
        if target_line not in lines:
            lines.append(target_line)
            new_content = "\n".join(lines) + "\n"
            self.write_file(blacklist_path, new_content)

        code_lsmod, lsmod_out, _ = self.run(["lsmod"], check=False)
        if code_lsmod == 0 and any(line.startswith(module + " ") for line in lsmod_out.splitlines()):
            return self.run(["modprobe", "-r", module], check=False)
        return 0, f"Module {module} blacklisted", ""

    def enable_hardware(self, module: str) -> Tuple[int, str, str]:
        if not MODULE_NAME_REGEX.match(module):
            return 1, "", f"Invalid module name: {module}"

        blacklist_path = "/etc/modprobe.d/parch-dm-blacklist.conf"
        code, out, _ = self.run(["cat", blacklist_path], check=False)
        if code == 0:
            lines = [l for l in out.splitlines() if not l.startswith(f"blacklist {module}")]
            new_content = "\n".join(lines) + ("\n" if lines else "")
            self.write_file(blacklist_path, new_content)

        return self.run(["modprobe", module], check=False)

