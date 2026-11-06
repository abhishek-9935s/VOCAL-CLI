"""Run the real CLI and PTY runner with a fake proposal, never a live API."""
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(os.name == "nt", reason="POSIX PTY integration test")
def test_review_card_requires_approval_before_execution(tmp_path):
    marker = tmp_path / "executed"
    script = r'''
import os, pty, select, shlex, signal, sys, time
marker = sys.argv[1]
pid, fd = pty.fork()
if pid == 0:
    from vocal import cli
    from vocal.context.collector import EnvironmentContext
    from vocal.engine.schema import CommandProposal
    os.environ["SHELL"] = "/bin/sh"
    cli.get_settings = lambda: {}
    cli.ContextCollector.collect = lambda self: EnvironmentContext(os="Linux", shell="sh", cwd=os.getcwd())
    cli.generate_proposal = lambda *args: CommandProposal(command="printf executed > " + shlex.quote(marker), explanation="Write a test marker", risk_level="LOW", target_binary="printf", requires_sudo=False, is_destructive=False)
    sys.argv = ["vocal", "ask", "test request"]
    cli.app()
    os._exit(0)
output = b""
sent = False
end = time.monotonic() + 8
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
    if b" Cancel" in output and not sent:
        assert not os.path.exists(marker), "command ran before approval"
        os.write(fd, b"\r")
        sent = True
else:
    os.kill(pid, signal.SIGKILL)
_, status = os.waitpid(pid, 0)
assert sent, output
assert os.waitstatus_to_exitcode(status) == 0, (status, output)
assert open(marker).read() == "executed"
'''
    result = subprocess.run([sys.executable, "-c", script, str(marker)], capture_output=True, text=True, timeout=12)
    assert result.returncode == 0, result.stderr
