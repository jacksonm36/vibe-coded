"""Run Ansible playbooks or scripts (shell, PowerShell, Python, etc.) and capture output."""
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app import crud

# Script extensions and the command to run them (interpreter + optional args).
# .yml and .yaml are NOT here — they always run as native Ansible playbooks (ansible-playbook).
SCRIPT_RUNNERS = {
    ".sh": ["bash"],
    ".bash": ["bash"],
    ".zsh": ["zsh"],
    ".csh": ["csh"],
    ".ksh": ["ksh"],
    ".ps1": ["powershell", "-ExecutionPolicy", "Bypass", "-File"],
    ".psm1": ["powershell", "-ExecutionPolicy", "Bypass", "-File"],
    ".bat": ["cmd", "/c"],
    ".cmd": ["cmd", "/c"],
    ".py": ["python3"],
    ".rb": ["ruby"],
}


def _is_script(path: str) -> bool:
    """True if path is a script (e.g. .sh, .ps1); False for .yml/.yaml (native Ansible playbooks)."""
    ext = Path(path).suffix.lower()
    return ext in SCRIPT_RUNNERS


def _run_script(
    script_path: str,
    extra_vars: str,
    timeout: int = 3600,
) -> tuple[int, str]:
    """Run a script with the appropriate interpreter. Returns (returncode, output)."""
    ext = Path(script_path).suffix.lower()
    runner = list(SCRIPT_RUNNERS.get(ext, []))
    if not runner:
        return 1, f"No runner for extension {ext}."

    abs_path = os.path.abspath(script_path)
    if not os.path.isfile(abs_path):
        return 1, f"Script not found: {abs_path}"

    cwd = os.path.dirname(abs_path)
    # Prefer pwsh on non-Windows for PowerShell scripts
    if ext in (".ps1", ".psm1") and os.name != "nt":
        try:
            subprocess.run(["pwsh", "--version"], capture_output=True, timeout=2)
            runner = ["pwsh", "-ExecutionPolicy", "Bypass", "-File"]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    cmd = runner + [abs_path]

    # On Windows, prefer python over python3 if we're running .py
    if ext == ".py" and os.name == "nt":
        try:
            subprocess.run(["python", "--version"], capture_output=True, timeout=2)
            cmd = ["python", abs_path]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    env = os.environ.copy()
    if extra_vars and extra_vars.strip():
        for line in extra_vars.strip().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                key = key.strip()
                if key:
                    env[key] = val.strip().strip('"').strip("'")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        env=env,
    )
    out, _ = proc.communicate(timeout=timeout)
    return proc.returncode, (out or "")


def run_playbook(
    db: Session,
    job_id: int,
    playbook_path: str,
    inventory_content: str,
    extra_vars: str = "",
    credential_ssh_key: Optional[str] = None,
    credential_ssh_password: Optional[str] = None,
    credential_vault_password: Optional[str] = None,
) -> tuple[str, str]:
    """
    Run ansible-playbook in a subprocess.
    - credential_ssh_key: private key content → temp file, pass --private-key
    - credential_ssh_password: use SSHPASS + sshpass -e (requires sshpass on Linux/macOS)
    Returns (status, output_log).
    """
    crud.update_job_status(db, job_id, "running", "")

    # Run as script (shell, PowerShell, Python, etc.) if path has a script extension
    if _is_script(playbook_path):
        try:
            code, out = _run_script(playbook_path, extra_vars or "")
            status = "success" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            out = "Job timed out after 3600s."
            status = "failed"
        except Exception as e:
            out = str(e)
            status = "failed"
        crud.update_job_status(db, job_id, status, out)
        return status, out

    inv_file = None
    key_file = None
    vault_file = None
    extra_vars_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            inv_file = f.name
            f.write(inventory_content or "[all]\nlocalhost ansible_connection=local\n")

        cmd = ["ansible-playbook", playbook_path, "-i", inv_file]
        if extra_vars and extra_vars.strip():
            cmd.extend(["-e", extra_vars.strip()])

        if credential_ssh_key:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as kf:
                key_file = kf.name
                kf.write(credential_ssh_key.strip())
                if not credential_ssh_key.strip().endswith("\n"):
                    kf.write("\n")
            # Restrict to owner read/write only (SSH client requires this)
            os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
            cmd.extend(["--private-key", key_file])

        if credential_vault_password:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".vault", delete=False) as vf:
                vault_file = vf.name
                vf.write(credential_vault_password.strip() + "\n")
            # Restrict to owner read/write only
            os.chmod(vault_file, stat.S_IRUSR | stat.S_IWUSR)
            cmd.extend(["--vault-password-file", vault_file])

        cwd = os.path.dirname(os.path.abspath(playbook_path)) or "."
        env = os.environ.copy()

        # SSH password: pass via extra vars file (Ansible uses ansible_password / ansible_ssh_pass)
        extra_vars_file = None
        if credential_ssh_password:
            escaped = credential_ssh_password.replace("\\", "\\\\").replace('"', '\\"')
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as evf:
                extra_vars_file = evf.name
                evf.write(f'ansible_ssh_pass: "{escaped}"\nansible_password: "{escaped}"\n')
            # Restrict to owner read/write only
            os.chmod(extra_vars_file, stat.S_IRUSR | stat.S_IWUSR)
            cmd.extend(["-e", f"@{extra_vars_file}"])

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            env=env,
        )
        out, _ = proc.communicate(timeout=3600)
        out = out or ""
        status = "success" if proc.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        proc.kill()
        out = "Job timed out after 3600s."
        status = "failed"
    except FileNotFoundError as e:
        out = str(e)
        if "ansible-playbook" in out:
            out = "ansible-playbook not found. Install Ansible (e.g. pip install ansible)."
        status = "failed"
    except Exception as e:
        out = str(e)
        status = "failed"
    finally:
        for f in (inv_file, key_file, vault_file, extra_vars_file):
            if f and os.path.exists(f):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    crud.update_job_status(db, job_id, status, out)
    return status, out
