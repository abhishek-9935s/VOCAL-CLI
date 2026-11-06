"""Discover the invoking shell and a bounded set of filesystem/tool metadata."""
import heapq
import os
import platform
import shutil
from pathlib import Path

import psutil

TOOLS = ("git", "docker", "kubectl", "node", "npm", "pnpm", "yarn", "python", "python3", "go", "lsof")
SHELL_NAMES = {"sh", "bash", "zsh", "fish", "dash", "ksh", "csh", "tcsh", "cmd", "powershell", "pwsh"}


def _is_shell(name: str) -> bool:
    return Path(name).name.lower().removesuffix(".exe") in SHELL_NAMES


def shell_executable() -> str:
    """Prefer the actual parent shell, falling back to the login shell or OS default.

    An intermediate process (IDE, script, etc.) may obscure the invoking shell; the
    fallback cannot reliably recover it in that case. Context and execution use the
    same result so the model is not told to target a different shell from the runner.
    """
    try:
        parent = psutil.Process().parent()
        if parent is not None:
            name = parent.name()
            if _is_shell(name):
                try:
                    path = parent.exe()
                except (psutil.Error, OSError):
                    path = ""
                return path or shutil.which(name) or name
    except (OSError, psutil.Error):
        pass
    if os.name == "nt":
        return os.environ.get("COMSPEC") or "cmd.exe"
    return os.environ.get("SHELL") or "/bin/sh"


def active_shell() -> str:
    return Path(shell_executable()).name


def system_context() -> dict:
    cwd = os.getcwd()
    try:
        # Avoid allocating the entire listing of very large directories.
        paths = heapq.nsmallest(30, (p for p in Path(cwd).iterdir() if not p.name.startswith(".")), key=lambda p: p.name)
        entries = [p.name + ("/" if p.is_dir() else "") for p in paths]
    except OSError:
        entries = []
    return {"os": platform.system(), "os_release": platform.release(), "shell": active_shell(),
            "cwd": cwd, "dir_contents": entries,
            "installed_binaries": [tool for tool in TOOLS if shutil.which(tool)]}
