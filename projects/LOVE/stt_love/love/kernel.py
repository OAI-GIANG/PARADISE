from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shlex
import signal
import subprocess
import sys
import time
from typing import Sequence

MAX_OUTPUT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ExecutionResult:
    command: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    argv: tuple[str, ...]


class LOVEKernel:
    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.allowed_executables = {str(Path(sys.executable).resolve())}

    def write_text(self, relative: str, content: str) -> Path:
        path = (self.workspace / relative).resolve()
        if self.workspace not in path.parents and path != self.workspace:
            raise PermissionError("path escapes workspace")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _normalize_argv(self, command: Sequence[str] | str) -> list[str]:
        if isinstance(command, str):
            argv = [token.strip('"\'') for token in shlex.split(command, posix=(os.name != "nt"))]
        else:
            argv = [str(item) for item in command]
        if not argv or not argv[0].strip():
            raise ValueError("argv is required")
        executable = str(Path(argv[0]).resolve()) if os.path.isabs(argv[0]) else ""
        if executable not in self.allowed_executables:
            raise PermissionError("executable is not allow-listed")
        return argv

    @staticmethod
    def _display_command(argv: Sequence[str]) -> str:
        if os.name == "nt":
            return subprocess.list2cmdline(list(argv))
        return shlex.join(list(argv))

    def run(self, command: Sequence[str] | str, timeout_s: float = 10.0) -> ExecutionResult:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        argv = self._normalize_argv(command)
        started = time.monotonic()
        creationflags = 0
        kwargs = {}
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(
            argv,
            cwd=self.workspace,
            shell=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
            **kwargs,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
            returncode = proc.returncode
        except subprocess.TimeoutExpired as exc:
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            stdout, stderr = proc.communicate()
            returncode = -signal.SIGKILL if os.name != "nt" else -1
            stdout = (stdout or "") if stdout is not None else (exc.stdout or "")
            stderr = (stderr or "") if stderr is not None else (exc.stderr or "")
            raise TimeoutError("execution timeout; process group terminated") from exc
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
        truncated_stdout = len(stdout.encode("utf-8", errors="replace")) > MAX_OUTPUT_BYTES
        truncated_stderr = len(stderr.encode("utf-8", errors="replace")) > MAX_OUTPUT_BYTES
        if truncated_stdout:
            stdout = stdout.encode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore")
        if truncated_stderr:
            stderr = stderr.encode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore")
        if truncated_stdout:
            stderr += "\n[LOVE_OUTPUT_TRUNCATED_STDOUT]"
        if truncated_stderr:
            stderr += "\n[LOVE_OUTPUT_TRUNCATED_STDERR]"
        return ExecutionResult(
            command=self._display_command(argv),
            cwd=str(self.workspace),
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            argv=tuple(argv),
        )
