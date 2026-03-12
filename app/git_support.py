"""Git clone/pull for project repositories (GitHub, GitLab, etc.)."""
import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.parse
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Workspace root for cloned repos (one dir per project)
WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"

# Allowlist for valid Git branch/tag name characters
_BRANCH_RE = re.compile(r'^[a-zA-Z0-9._\-/]+$')

# File patterns we treat as runnable artifacts (Ansible, shell, Terraform, automation, etc.)
SUPPORTED_FILE_PATTERNS: tuple[str, ...] = (
    # Ansible / YAML
    "*.yml",
    "*.yaml",
    # Shell / Bash
    "*.sh",
    "*.bash",
    "*.zsh",
    "*.csh",
    "*.ksh",
    # Windows scripts
    "*.ps1",
    "*.psm1",
    "*.bat",
    "*.cmd",
    # Terraform / HCL
    "*.tf",
    "*.tfvars",
    "*.tf.json",
    "*.hcl",
    # Other automation / config
    "*.py",
    "*.rb",
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
            "Invalid branch name. Only alphanumeric characters, "
            "hyphens, underscores, dots, and slashes are allowed."
        )
    if branch.startswith('-') or branch.startswith('..') or '..' in branch:
        raise ValueError("Invalid branch name.")
    return branch


def validate_branch(branch: str) -> str:
    """Public validation for branch/tag names. Raises ValueError if invalid."""
    return _validate_branch((branch or "").strip() or "main")


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
    For SSH URLs uses GIT_SSH_COMMAND with ssh -i <keyfile>.
    For HTTPS URLs uses a temporary git-credentials store so the token is
    never exposed in command-line arguments (process list / logs).
    """
    raw = git_url.strip()
    if not raw:
        raise ValueError("git_url is required")
    url = normalize_git_url(raw)
    branch = validate_branch(branch or "main")
    repo_path = _workspace_path(project_id)

    env = os.environ.copy()
    key_file = None
    creds_file = None
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
        # Use a temporary git-credentials store file so the token is not visible
        # in the process argument list or git error messages.
        parsed = urllib.parse.urlparse(url)
        cred_entry = f"{parsed.scheme}://x-access-token:{https_token}@{parsed.netloc}\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".git-credentials", delete=False) as f:
            f.write(cred_entry)
            creds_file = f.name
        os.chmod(creds_file, stat.S_IRUSR | stat.S_IWUSR)
        # Point git at our temporary credentials store; disable any system helper first,
        # then activate the store so system/user credential helpers are not used.
        env["GIT_CONFIG_COUNT"] = "2"
        env["GIT_CONFIG_KEY_0"] = "credential.helper"
        env["GIT_CONFIG_VALUE_0"] = ""  # Clear any pre-configured system/user helpers
        env["GIT_CONFIG_KEY_1"] = "credential.helper"
        env["GIT_CONFIG_VALUE_1"] = f"store --file={creds_file}"
        # Disable interactive prompts so failures surface immediately.
        env["GIT_TERMINAL_PROMPT"] = "0"

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
        for f in (key_file, creds_file):
            if f and os.path.exists(f):
                try:
                    os.unlink(f)
                except OSError:
                    pass


# Lowercase suffixes for case-insensitive walk (single extension only; *.tf.json handled by glob)
_WALK_SUFFIXES: frozenset[str] = frozenset(
    (
        ".yml", ".yaml",
        ".sh", ".bash", ".zsh", ".csh", ".ksh",
        ".ps1", ".psm1", ".bat", ".cmd",
        ".tf", ".tfvars", ".hcl",
        ".py", ".rb",
    )
)


def _should_skip_path(rel: Path) -> bool:
    """Skip hidden dirs, .git, and Ansible var dirs."""
    for part in rel.parts:
        if part.startswith(".") or part in ("group_vars", "host_vars"):
            return True
    return False


def list_playbooks_in_repo(repo_path: Path) -> list[str]:
    """
    Return relative paths of supported files under repo root.
    Includes Ansible playbooks, shell scripts, Terraform, PowerShell, Python, etc.
    Uses both glob patterns and a case-insensitive walk so storage repos with
    mixed extensions (e.g. .SH, .ps1, .YML) are all found.
    """
    seen: set[str] = set()
    playbooks: list[str] = []

    # 1) Glob by pattern (primary)
    for ext in SUPPORTED_FILE_PATTERNS:
        for f in repo_path.rglob(ext):
            if f.is_file():
                try:
                    rel = f.relative_to(repo_path)
                except ValueError:
                    continue
                if _should_skip_path(rel):
                    continue
                key = str(rel).replace("\\", "/")
                if key not in seen:
                    seen.add(key)
                    playbooks.append(key)

    # 2) Walk repo and add by suffix (case-insensitive) so .SH, .YML, .PS1, etc. are found
    for root, _dirs, files in os.walk(repo_path, topdown=True):
        root_path = Path(root)
        try:
            rel_root = root_path.relative_to(repo_path)
        except ValueError:
            continue
        if _should_skip_path(rel_root):
            _dirs[:] = []
            continue
        for name in files:
            if name.startswith("."):
                continue
            suffix = Path(name).suffix.lower()
            if suffix and suffix in _WALK_SUFFIXES:
                rel_file = rel_root / name
                key = str(rel_file).replace("\\", "/")
                if key not in seen:
                    seen.add(key)
                    playbooks.append(key)

    # Sort: native Ansible playbooks (.yml/.yaml) first, then the rest alphabetically
    def _sort_key(p: str) -> tuple[int, str]:
        lower = p.lower()
        is_ansible = 0 if (lower.endswith(".yml") or lower.endswith(".yaml")) else 1
        return (is_ansible, p)

    return sorted(playbooks, key=_sort_key)
