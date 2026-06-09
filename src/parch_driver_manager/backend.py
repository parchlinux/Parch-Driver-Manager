import logging
import shlex
import subprocess
from typing import List, Tuple

from .system_prober import CommandError

logger = logging.getLogger(__name__)


class BackendRunner:
    def __init__(self, use_pkexec: bool = True):
        self.use_pkexec = use_pkexec

    def _build_command(self, cmd: List[str]) -> List[str]:
        if self.use_pkexec:
            return ["pkexec"] + cmd
        return cmd

    def run(self, cmd: List[str], check: bool = True) -> Tuple[int, str, str]:
        full_cmd = self._build_command(cmd)
        logger.debug("BackendRunner executing: %s", ' '.join(full_cmd))
        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = proc.communicate()
        if check and proc.returncode != 0:
            raise CommandError(full_cmd, proc.returncode, out, err)
        return proc.returncode, out, err

    def disable_hardware(self, module: str) -> Tuple[int, str, str]:
        blacklist_path = "/etc/modprobe.d/parch-dm-blacklist.conf"
        quoted_module = shlex.quote(module)
        quoted_path = shlex.quote(blacklist_path)
        bash_cmd = f"""
        if ! grep -q '^blacklist {quoted_module}$' {quoted_path} 2>/dev/null; then
            echo "blacklist {quoted_module}" >> {quoted_path}
        fi
        modprobe -r {quoted_module}
        """
        return self.run(["bash", "-c", bash_cmd], check=False)

    def enable_hardware(self, module: str) -> Tuple[int, str, str]:
        blacklist_path = "/etc/modprobe.d/parch-dm-blacklist.conf"
        quoted_module = shlex.quote(module)
        quoted_path = shlex.quote(blacklist_path)
        bash_cmd = f"""
        if [ -f {quoted_path} ]; then
            sed -i '/^blacklist {quoted_module}/d' {quoted_path}
        fi
        modprobe {quoted_module}
        """
        return self.run(["bash", "-c", bash_cmd], check=False)
