"""Git probes have bounded runtime and never use a shell."""
import subprocess


def _git(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL, text=True, timeout=0.5).rstrip("\r\n")
    except (OSError, subprocess.SubprocessError):
        return None


def git_context() -> dict:
    empty = {"is_git_repo": False, "git_root": None, "git_branch": None,
             "git_detached": False, "git_status_summary": None, "git_dirty_count": None,
             "git_staged_count": None, "git_unstaged_count": None, "git_untracked_count": None, "git_recent_commits": [], "git_stashes": []}
    if _git("rev-parse", "--is-inside-work-tree") != "true":
        return empty
    branch = _git("branch", "--show-current")
    status = _git("status", "--porcelain")
    commits = _git("log", "-n", "3", "--oneline")
    root = _git("rev-parse", "--show-toplevel")
    stashes = _git("stash", "list", "-n", "10", "--format=%gd")
    lines = status.splitlines() if status is not None else []
    staged = sum(1 for line in lines if len(line) >= 2 and line[0] not in (" ", "?", "!"))
    unstaged = sum(1 for line in lines if len(line) >= 2 and line[1] not in (" ", "?", "!"))
    untracked = sum(1 for line in lines if line.startswith("??"))
    # Limit provider input even in very large repositories.
    summary = "\n".join(lines[:100]) if status is not None else None
    if summary is not None and (len(lines) > 100 or len(summary) > 12000):
        summary = summary[:12000] + "\n[status truncated]"
    return {"is_git_repo": True, "git_root": root, "git_branch": branch or None,
            "git_detached": branch == "", "git_status_summary": summary,
            "git_dirty_count": len(lines) if status is not None else None,
            "git_staged_count": staged if status is not None else None,
            "git_unstaged_count": unstaged if status is not None else None,
            "git_untracked_count": untracked if status is not None else None,
            "git_recent_commits": commits.splitlines() if commits else [],
            "git_stashes": stashes.splitlines() if stashes else []}
