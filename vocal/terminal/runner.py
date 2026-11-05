"""Run commands in a child shell, forwarding terminal input and output."""
import os
import subprocess
import sys
from collections import deque
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    exit_code: int
    output_tail: str


def _tail(chunks) -> str:
    text = b"".join(chunks).decode(errors="replace")
    return "\n".join(text.splitlines()[-20:])[-16000:]


def _shell_command(command: str) -> list[str]:
    from ..context.system import shell_executable
    shell = shell_executable()
    if os.name == "nt":
        if "powershell" in shell.lower() or "pwsh" in shell.lower():
            return [shell, "-NoProfile", "-Command", command]
        return [shell, "/c", command]
    return [shell, "-c", command]


def run_command(command: str) -> ExecutionResult:
    # For redirected streams and Windows, use a pipe and retain a combined output tail.
    if os.name == "nt" or not (sys.stdin.isatty() and sys.stdout.isatty()):
        proc = subprocess.Popen(_shell_command(command), stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        chunks = deque(maxlen=100)
        assert proc.stdout is not None
        try:
            while True:
                chunk = proc.stdout.read1(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if hasattr(sys.stdout, "buffer"):
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                else:
                    sys.stdout.write(chunk.decode(errors="replace"))
                    sys.stdout.flush()
            code = proc.wait()
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        return ExecutionResult(code, _tail(chunks))

    import pty
    import select
    import termios
    import tty
    import fcntl
    import struct
    import signal
    import errno

    master, slave = pty.openpty()
    stdin_fd = sys.stdin.fileno()
    previous = termios.tcgetattr(stdin_fd)
    old_winch = signal.getsignal(signal.SIGWINCH)
    proc = None
    chunks = deque(maxlen=100)

    def resize(*_args):
        try:
            size = fcntl.ioctl(stdin_fd, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
            fcntl.ioctl(master, termios.TIOCSWINSZ, size)
        except OSError:
            pass

    try:
        resize()
        def attach_tty():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

        proc = subprocess.Popen(_shell_command(command), stdin=slave, stdout=slave, stderr=slave, preexec_fn=attach_tty)
        os.close(slave)
        slave = -1
        signal.signal(signal.SIGWINCH, resize)
        tty.setraw(stdin_fd, when=termios.TCSANOW)
        while True:
            readable, _, _ = select.select([master, stdin_fd], [], [])
            if master in readable:
                try:
                    data = os.read(master, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not data:
                    break
                chunks.append(data)
                os.write(sys.stdout.fileno(), data)
            if stdin_fd in readable:
                data = os.read(stdin_fd, 4096)
                if data:
                    os.write(master, data)
        code = proc.wait()
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, previous)
        signal.signal(signal.SIGWINCH, old_winch)
        os.close(master)
        if slave >= 0:
            os.close(slave)
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            except ProcessLookupError:
                proc.wait()
    return ExecutionResult(code, _tail(chunks))
