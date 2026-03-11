"""Git clone/pull for project repositories (GitHub, GitLab, etc.)."""
import logging
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Workspace root for cloned repos (one dir per project)
WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"

# Allowlist for valid Git branch/tag name characters
_BRANCH_RE = re.compile(r'^[a-zA-Z0-9._\-/]+$')

# File patterns we treat as runnable artifacts (Ansible, shell, Terraform, etc.)
SUPPORTED_FILE_PATTERNS: tuple[str, ...] = (
    "*.yml",
    "*.yaml",
    "*.sh",
    "*.bash",
    "*.ps1",
    "*.tf",
    "*.tfvars",
    "*.tf.json",
)


def _workspace_path(project_id: int) -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_DIR / f"project_{project_id}"


def _validate_branch(branch: str) -> str:
    """
    Validate a Git branch/tag name to prevent command-option injection.
    Raises ValueError if the name contains unsafe characters.
    """
    if not branch or not _BRANCH_RE.match(branch):
        raise ValueError(
            f"Invalid branch name {branch!r}. Only alphanumeric characters, "
            "hyphens, underscores, dots, and slashes are allowed."
        )
    # Prevent names that start with '-' (would be interpreted as git options)
    # or '..' (path traversal in refspecs).
    if branch.startswith('-') or branch.startswith('..') or '..' in branch:
        raise ValueError(f"Invalid branch name {branch!r}.")
    return branch


def _is_ssh_url(url: str) -> bool:
    return url.strip().startswith("git@") or "git@" in url.split("://")[0]


def normalize_git_url(url: str) -> str:
    """
    Convert GitHub/GitLab browser URLs to clone URLs.
    e.g. https://github.com/owner/repo/blob/main/path -> https://github.com/owner/repo.git
    """
    u = url.strip()
    if not u:
        return u
    # GitHub: .../owner/repo/blob/branch/path or .../owner/repo/tree/branch/path
    m = re.match(r"^(https?://(?:www\.)?github\.com/[^/]+/[^/]+?)(?:/blob/[^/]+/.*|/tree/[^/]+/.*)?/?$", u, re.I)
    if m:
        base = m.group(1).rstrip("/")
        return base if base.endswith(".git") else f"{base}.git"
    # GitLab: .../owner/repo/-/blob/branch/path
    m = re.match(r"^(https?://[^/]+/[^/]+/[^/]+?)(?:/-/blob/.*|/-/tree/.*)?/?$", u, re.I)
    if m:
        base = m.group(1).rstrip("/")
        return base if base.endswith(".git") else f"{base}.git"
    return u


def clone_or_pull(
    project_id: int,
    git_url: str,
    branch: str = "main",
    ssh_private_key: Optional[str] = None,
    https_token: Optional[str] = None,
) -> Path:
    """
    Clone the repo if not present, else pull. Return path to repo root.
    For SSH URL uses GIT_SSH_COMMAND with ssh -i <keyfile>.
    For HTTPS URL injects token as https://<token>@host/path.
    """
    raw = git_url.strip()
    if not raw:
        raise ValueError("git_url is required")
    url = normalize_git_url(raw)
    branch = _validate_branch((branch or "main").strip())
    repo_path = _workspace_path(project_id)

    env = os.environ.copy()
    key_file = None
    if _is_ssh_url(url) and ssh_private_key:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as f:
            f.write(ssh_private_key.strip())
            if not ssh_private_key.strip().endswith("\n"):
                f.write("\n")
            key_file = f.name
        # Restrict key file to owner-read/write only (SSH requires this)
        os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
        env["GIT_SSH_COMMAND"] = f'ssh -i "{key_file}" -o StrictHostKeyChecking=accept-new'
    elif not _is_ssh_url(url) and https_token:
        # Inject token: https://x-access-token:TOKEN@host/path
        # The token is passed via the URL; git may include it in error messages.
        if "://" in url:
            scheme, rest = url.split("://", 1)
            url = f"{scheme}://x-access-token:{https_token}@{rest}"
        else:
            url = f"https://x-access-token:{https_token}@{url}"

    try:
        if repo_path.exists() and (repo_path / ".git").exists():
            subprocess.run(
                ["git", "fetch", "origin", branch],
                cwd=repo_path,
                env=env,
                check=True,
                capture_output=True,
                timeout=60,
            )
            subprocess.run(
                ["git", "checkout", branch],
                cwd=repo_path,
                check=True,
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "pull", "origin", branch],
                cwd=repo_path,
                env=env,
                check=True,
                capture_output=True,
                timeout=120,
            )
        else:
            if repo_path.exists():
                import shutil
                shutil.rmtree(repo_path)
            subprocess.run(
                ["git", "clone", "--branch", branch, "--single-branch", "--depth", "50", url, str(repo_path)],
                env=env,
                check=True,
                capture_output=True,
                timeout=300,
            )
        return repo_path
    finally:
        if key_file and os.path.exists(key_file):
            try:
                os.unlink(key_file)
            except OSError:
                pass


def list_playbooks_in_repo(repo_path: Path) -> list[str]:
    """
    Return relative paths of supported files under repo root.
    Includes Ansible playbooks, shell scripts, and Terraform files for Job Templates.
    """
    playbooks: list[str] = []
    for ext in SUPPORTED_FILE_PATTERNS:
        for f in repo_path.rglob(ext):
            if f.is_file():
                rel = f.relative_to(repo_path)
                if any(part.startswith(".") for part in rel.parts):
                    continue
                if "group_vars" in rel.parts or "host_vars" in rel.parts:
                    continue
                playbooks.append(str(rel).replace("\\", "/"))
    return sorted(dict.fromkeys(playbooks))
