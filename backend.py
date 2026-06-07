import subprocess
from typing import List, Tuple
from system_prober import CommandError, debug_log

class BackendRunner:
    def __init__(self, use_pkexec: bool = True):
        self.use_pkexec = use_pkexec

    def _build_command(self, cmd: List[str]) -> List[str]:
        if self.use_pkexec:
            return ["pkexec"] + cmd
        return cmd

    def run(self, cmd: List[str], check: bool = True) -> Tuple[int, str, str]:
        full_cmd = self._build_command(cmd)
        debug_log(f"BackendRunner executing: {' '.join(full_cmd)}")
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
        bash_cmd = f"""
        if ! grep -q '^blacklist {module}$' {blacklist_path} 2>/dev/null; then
            echo "blacklist {module}" >> {blacklist_path}
        fi
        modprobe -r {module}
        """
        return self.run(["bash", "-c", bash_cmd], check=False)

    def enable_hardware(self, module: str) -> Tuple[int, str, str]:
        blacklist_path = "/etc/modprobe.d/parch-dm-blacklist.conf"
        bash_cmd = f"""
        if [ -f {blacklist_path} ]; then
            sed -i '/^blacklist {module}/d' {blacklist_path}
        fi
        modprobe {module}
        """
        return self.run(["bash", "-c", bash_cmd], check=False)
