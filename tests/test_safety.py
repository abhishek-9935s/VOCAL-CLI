import pytest
from vocal.safety.validator import validate_command


@pytest.mark.parametrize("command", [
    "rm -rf /", "rm -fr /*", "sudo rm -r -f ~/stuff", "rm --recursive --force ../foo",
    "echo yes; /bin/rm -rf /tmp/foo", ":(){ :|:& };:",
    "dd if=foo of=/dev/sda", "dd if=foo of=/dev/nvme0n1", "mkfs.ext4 /dev/sda1", "chmod -R 777 /",
])
def test_critical_patterns_are_blocked(command):
    result = validate_command(command)
    assert result.risk_level == "CRITICAL"
    assert result.blocked


@pytest.mark.parametrize("command", ["git push -f origin main", "git push origin main --force", "git push --force-with-lease", "git clean -fd", "docker system prune -a", "docker volume prune", "kill -9 1", "pkill node"])
def test_high_risk_patterns(command):
    assert validate_command(command).risk_level == "HIGH"


def test_safe_command_and_model_escalation():
    assert validate_command("git status").risk_level == "LOW"
    assert validate_command("git status", "HIGH").risk_level == "HIGH"
    assert validate_command("git status", "LOW", destructive=True).risk_level == "HIGH"


def test_invalid_and_missing_binary():
    assert validate_command("echo 'unterminated").blocked
    assert "not found" in validate_command("vocal_missing_binary_xyz").warnings[0]


@pytest.mark.parametrize("command", [
    "git -C /repo push -f origin main", "git -c push.default=current push origin +main",
    "git push origin +HEAD:main", "git push --force-with-lease=main origin main",
])
def test_force_push_with_global_options_and_refspec(command):
    assert validate_command(command).risk_level == "HIGH"


@pytest.mark.parametrize("character", ["\x1b", "\r", "\x07", "\u202e", "\u200b", "\u2028"])
def test_hidden_or_terminal_control_characters_blocked(character):
    result = validate_command("echo safe" + character + "text")
    assert result.blocked
    assert "control" in result.warnings[0]
