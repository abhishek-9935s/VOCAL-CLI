"""Heuristics for common dangerous operations, not a shell sandbox."""
import re

CRITICAL = [
    (r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb"),
    (r"\bdd\b[^\n;|&]*\bof\s*=\s*['\"]?/dev/(?:sd[a-z]|nvme|hd[a-z]|null)", "Raw device overwrite"),
    (r"\bmkfs(?:\.[\w]+)?\b[^\n;|&]*/dev/", "Filesystem formatting"),
    (r"\bchmod\b[^\n;|&]*\b777\s+['\"]?/", "Unrestricted permissions on an absolute path"),
]
HIGH = [
    (r"\brm\b[^\n;|&]*(?:--recursive\b|(?<!\S)-[a-zA-Z]*[rR][a-zA-Z]*\b)", "Recursive deletion can permanently remove files"),
    (r"\bgit\s+reset\b[^\n;|&]*--hard\b", "Hard reset discards tracked changes"),
    (r"\bgit\s+(?:-\S+\s+)*push\b[^\n;|&]*(?:--force(?:-with-lease)?\b|(?<!\S)-[a-zA-Z]*f[a-zA-Z]*\b)", "Force push may overwrite remote history"),
    (r"\bgit\s+clean\b[^\n;|&]*(?:--force\b|(?<!\S)-[a-zA-Z]*f[a-zA-Z]*\b)", "Git clean can permanently delete files"),
    (r"\bdocker\s+(?:system\s+prune|volume\s+prune|rm\s+-f\s+\$\(docker)", "Docker cleanup can remove data"),
    (r"\bkill\s+-9\s+(?:-1|1)(?:\s|$|[;|&])", "Signal sent to critical or many processes"),
    (r"\b(?:pkill|killall)\b", "Broad process termination"),
]
