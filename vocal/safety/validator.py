import re
import shlex
import shutil
from dataclasses import dataclass
from .rules import CRITICAL, HIGH
from ..terminal.display import unsafe_character

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


@dataclass(frozen=True)
class SafetyAssessment:
    risk_level: str
    warnings: tuple[str, ...] = ()
    blocked: bool = False


def _dangerous_rm(command: str) -> bool:
    # Tokenize shell separators and substitutions too. This is deliberately conservative:
    # a recursive force delete involving a root, home, glob, or relative traversal is blocked.
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return True
    for i, token in enumerate(tokens):
        if token.rsplit("/", 1)[-1] != "rm":
            continue
        args = []
        for arg in tokens[i + 1:]:
            if arg and all(c in ";&|()" for c in arg):
                break
            args.append(arg)
        flags = [a for a in args if a.startswith("-") and a != "--"]
        recursive = any(a in ("--recursive", "--directory") or (a.startswith("-") and not a.startswith("--") and ("r" in a or "R" in a)) for a in flags)
        force = any(a == "--force" or (a.startswith("-") and not a.startswith("--") and "f" in a) for a in flags)
        paths = [a for a in args if not a.startswith("-")]
        if recursive and force and (not paths or any(p.startswith(("/", "~", "./", "../")) or any(c in p for c in "*?[") or "$" in p for p in paths)):
            return True
    return False


def _git_force_push(command: str) -> bool:
    """Recognize common force-push forms, including Git global options and +refspecs."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return False
    for i, token in enumerate(tokens):
        if token.rsplit("/", 1)[-1] != "git":
            continue
        args = []
        for arg in tokens[i + 1:]:
            if arg and all(c in ";&|()" for c in arg):
                break
            args.append(arg)
        # Skip common global options and their arguments before the subcommand.
        j = 0
        while j < len(args) and args[j].startswith("-"):
            flag = args[j]
            if flag in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"):
                j += 2
            else:
                j += 1
        if j >= len(args) or args[j] != "push":
            continue
        for arg in args[j + 1:]:
            if arg in ("--force", "--force-with-lease", "--force-if-includes") or arg.startswith("--force-with-lease="):
                return True
            if arg.startswith("-") and not arg.startswith("--") and "f" in arg[1:]:
                return True
            if arg.startswith("+") and len(arg) > 1:
                return True
    return False


def validate_command(command: str, model_risk: str = "LOW", destructive: bool = False) -> SafetyAssessment:
    warnings = []
    risk = model_risk if model_risk in LEVELS else "HIGH"
    if not command.strip():
        return SafetyAssessment("CRITICAL", ("Empty command",), True)
    if any(unsafe_character(char) for char in command):
        return SafetyAssessment("CRITICAL", ("Command contains control or invisible formatting characters",), True)
    if _dangerous_rm(command):
        warnings.append("Recursive forced deletion of a root, home, wildcard, or relative path")
    warnings.extend(description for pattern, description in CRITICAL if re.search(pattern, command, re.IGNORECASE))
    if warnings:
        return SafetyAssessment("CRITICAL", tuple(warnings), True)
    high = [description for pattern, description in HIGH if re.search(pattern, command, re.IGNORECASE)]
    if _git_force_push(command) and "Force push may overwrite remote history" not in high:
        high.append("Force push may overwrite remote history")
    if high:
        warnings.extend(high)
        risk = LEVELS[max(LEVELS.index(risk), LEVELS.index("HIGH"))]
    if destructive and LEVELS.index(risk) < LEVELS.index("HIGH"):
        risk = "HIGH"
    try:
        tokens = shlex.split(command, posix=True)
        first = tokens[0] if tokens else ""
        # Shell built-ins and assignments do not need a binary on PATH.
        builtins = {"cd", "echo", "export", "set", "unset", "pwd", "printf", "read", "test", "alias", "source", ".", "exit", "true", "false"}
        if first and first not in builtins and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", first) and not shutil.which(first):
            warnings.append(f"Binary '{first}' was not found on PATH (it may be a shell builtin).")
    except ValueError:
        return SafetyAssessment("CRITICAL", ("Cannot parse command safely",), True)
    return SafetyAssessment(risk, tuple(warnings), False)
