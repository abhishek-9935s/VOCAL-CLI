import subprocess
from unittest.mock import patch
from vocal.context.collector import ContextCollector
from vocal.context.git import git_context
from vocal.context.system import system_context


def test_context_outside_git():
    with patch("vocal.context.git.subprocess.check_output", side_effect=subprocess.CalledProcessError(128, "git")):
        result = ContextCollector().collect()
    assert result.os and result.shell and result.cwd
    assert not result.is_git_repo
    assert result.git_recent_commits == []


def test_git_context_extraction():
    values = ["true\n", "feature\n", " M file\n?? new\n", "abc first\ndef second\n", "/repo\n", "stash@{0}\n"]
    with patch("vocal.context.git.subprocess.check_output", side_effect=values) as mock:
        ctx = git_context()
    assert ctx["git_branch"] == "feature"
    assert ctx["git_status_summary"] == " M file\n?? new"
    assert len(ctx["git_recent_commits"]) == 2
    assert ctx["git_root"] == "/repo"
    assert ctx["git_stashes"] == ["stash@{0}"]
    assert all(call.kwargs["timeout"] == 0.5 for call in mock.call_args_list)


def test_git_detached_and_missing_log():
    with patch("vocal.context.git.subprocess.check_output", side_effect=["true", "", "", subprocess.CalledProcessError(1, "git"), "/repo", ""]):
        ctx = git_context()
    assert ctx["git_detached"]
    assert ctx["git_branch"] is None
    assert ctx["git_recent_commits"] == []


def test_directory_listing_is_limited_and_hidden_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for i in range(35):
        (tmp_path / f"file{i:02}").touch()
    (tmp_path / ".secret").touch()
    result = system_context()
    assert len(result["dir_contents"]) == 30
    assert ".secret" not in result["dir_contents"]


def test_git_counts_and_truncation():
    status = " M a\nM  b\n?? c\n" + "\n".join(f"?? file{i}" for i in range(105))
    with patch("vocal.context.git.subprocess.check_output", side_effect=["true", "main", status, "abc subject", "/repo", ""]):
        ctx = git_context()
    assert ctx["git_dirty_count"] == 108
    assert ctx["git_staged_count"] == 1
    assert ctx["git_unstaged_count"] == 1
    assert ctx["git_untracked_count"] == 106
    assert "[status truncated]" in ctx["git_status_summary"]


def test_parent_shell_is_used_for_context_and_execution(monkeypatch):
    import os
    from types import SimpleNamespace
    from vocal.context import system
    from vocal.terminal.runner import _shell_command
    if os.name == "nt":
        name, executable = "pwsh.exe", r"C:\Program Files\PowerShell\7\pwsh.exe"
    else:
        name, executable = "fish", "/usr/bin/fish"
    parent = SimpleNamespace(name=lambda: name, exe=lambda: executable)
    monkeypatch.setattr(system.psutil, "Process", lambda: SimpleNamespace(parent=lambda: parent))
    assert system.active_shell() == name
    assert _shell_command("echo hi")[0] == executable


def test_real_git_repository(tmp_path, monkeypatch):
    import shutil
    import pytest
    if not shutil.which("git"):
        pytest.skip("git is not installed")
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True)
    git("init", "-q")
    git("config", "user.email", "tests@example.invalid")
    git("config", "user.name", "VocalCLI tests")
    (tmp_path / "tracked.txt").write_text("initial\n")
    git("add", "tracked.txt")
    git("commit", "-qm", "initial")
    (tmp_path / "tracked.txt").write_text("stashed\n")
    git("stash", "push", "-qm", "test stash")
    (tmp_path / "tracked.txt").write_text("edited\n")
    (tmp_path / "untracked.txt").write_text("new\n")
    monkeypatch.chdir(tmp_path)
    context = ContextCollector().collect()
    assert context.is_git_repo
    assert context.git_branch
    assert context.git_dirty_count == 2
    assert context.git_unstaged_count == 1
    assert context.git_untracked_count == 1
    assert len(context.git_recent_commits) == 1
    assert context.git_stashes == ["stash@{0}"]
