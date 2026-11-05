from pydantic import BaseModel, Field
from .git import git_context
from .system import system_context


class EnvironmentContext(BaseModel):
    os: str
    os_release: str = ""
    shell: str
    cwd: str
    dir_contents: list[str] = Field(default_factory=list)
    is_git_repo: bool = False
    git_root: str | None = None
    git_branch: str | None = None
    git_detached: bool = False
    git_status_summary: str | None = None
    git_dirty_count: int | None = None
    git_staged_count: int | None = None
    git_unstaged_count: int | None = None
    git_untracked_count: int | None = None
    git_recent_commits: list[str] = Field(default_factory=list)
    git_stashes: list[str] = Field(default_factory=list)
    installed_binaries: list[str] = Field(default_factory=list)


class ContextCollector:
    def collect(self) -> EnvironmentContext:
        return EnvironmentContext(**system_context(), **git_context())
