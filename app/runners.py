"""Run Ansible playbooks and capture output."""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app import crud


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
            cmd.extend(["--private-key", key_file])

        if credential_vault_password:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".vault", delete=False) as vf:
                vault_file = vf.name
                vf.write(credential_vault_password.strip() + "\n")
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
