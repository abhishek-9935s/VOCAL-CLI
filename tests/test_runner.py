from vocal.terminal.runner import run_command


def test_non_interactive_execution_and_failure(capsys):
    import os
    import shlex
    import subprocess
    import sys
    args = [sys.executable, "-c", "print('first'); print('second'); raise SystemExit(7)"]
    command = subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)
    result = run_command(command)
    assert result.exit_code == 7
    assert "second" in result.output_tail


def test_posix_pty_forwards_terminal_input():
    import os
    import subprocess
    import sys
    import pytest
    if os.name == "nt":
        pytest.skip("POSIX PTY only")
    script = r'''
import os, pty, select, signal, time
pid, fd = pty.fork()
if pid == 0:
    os.environ["SHELL"] = "/bin/sh"
    from vocal.terminal.runner import run_command
    result = run_command("echo PROMPT; read x; echo ANSWER=$x")
    print("EXIT=", result.exit_code)
    os._exit(0 if result.exit_code == 0 else 1)
output = b""
end = time.monotonic() + 6
sent = False
while time.monotonic() < end:
    ready, _, _ = select.select([fd], [], [], 0.5)
    if not ready:
        continue
    try:
        data = os.read(fd, 4096)
    except OSError:
        break
    if not data:
        break
    output += data
    if b"PROMPT" in output and not sent:
        os.write(fd, b"hello\n")
        sent = True
else:
    os.kill(pid, signal.SIGKILL)
_, status = os.waitpid(pid, 0)
assert b"ANSWER=hello" in output, output
assert os.waitstatus_to_exitcode(status) == 0, (status, output)
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
