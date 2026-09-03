"""Execution seam shared by the Harness and deterministic Skill helpers.

The public interface intentionally contains only a context, a result, and an
adapter with one operation.  Command construction, output capture, timing, and
process failure classification remain behind the adapter seam.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Protocol, runtime_checkable


_SKILL_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_TERMINATION_GRACE_SECONDS = 0.5
_PROCESS_GATE_BOOTSTRAP = (
    "import os,sys\n"
    "fd=int(sys.argv[1])\n"
    "released=os.read(fd,1)\n"
    "os.close(fd)\n"
    "if not released: raise SystemExit(125)\n"
    "os.execv(sys.argv[2], sys.argv[2:])\n"
)


class SkillRuntimeError(RuntimeError):
    """Base class for errors raised by the Skill runtime."""


class InvalidSkillContextError(SkillRuntimeError):
    """The invocation context cannot be represented safely."""


class InvalidSkillPathError(InvalidSkillContextError):
    """An input or output is not a safe Workspace-relative path."""


class InvalidSkillAdapterError(SkillRuntimeError):
    """A repository Skill name cannot identify a safe adapter."""


class SkillExecutionError(SkillRuntimeError):
    """Base class for adapter failures with bounded execution diagnostics.

    Diagnostics deliberately contain no command/argv or environment mapping.
    ``stdout`` and ``stderr`` are retained verbatim because they are the Skill
    process's explicit diagnostic channels.
    """

    def __init__(
        self,
        message: str,
        *,
        adapter: str,
        stdout: str,
        stderr: str,
        elapsed_ms: float,
        exit_code: int | None,
    ) -> None:
        super().__init__(message)
        self.adapter = adapter
        self.stdout = stdout
        self.stderr = stderr
        self.elapsed_ms = elapsed_ms
        self.exit_code = exit_code


class SkillAdapterNotFoundError(SkillExecutionError):
    """The requested repository Skill has no executable ``run.py`` adapter."""


class SkillLaunchError(SkillExecutionError):
    """The adapter process could not be started."""


class SkillTimeoutError(SkillExecutionError):
    """The adapter exceeded its configured execution timeout."""


class SkillProcessError(SkillExecutionError):
    """The adapter completed with a non-zero exit code."""


class SkillHandlerError(SkillExecutionError):
    """An in-memory adapter handler raised an exception."""


@dataclass(frozen=True, slots=True, init=False)
class SkillContext:
    """One Skill invocation scoped to a single Workspace.

    ``inputs`` and ``outputs`` use portable POSIX-style paths relative to
    ``workspace``. Input directory markers ending in ``/`` are accepted and
    normalized; outputs and raw paths passed to :meth:`resolve` may not end in
    ``/``. Absolute paths, traversal, optional-output markers, and paths
    resolving through a symlink outside the Workspace are rejected.
    """

    workspace: Path
    unit_id: str
    inputs: tuple[PurePosixPath, ...] = ()
    outputs: tuple[PurePosixPath, ...] = ()
    checkpoint: str = ""

    def __init__(
        self,
        *,
        workspace: str | os.PathLike[str],
        unit_id: str,
        inputs: Iterable[str | os.PathLike[str]] = (),
        outputs: Iterable[str | os.PathLike[str]] = (),
        checkpoint: str = "",
    ) -> None:
        workspace_path = Path(workspace).expanduser().resolve()
        if not workspace_path.is_dir():
            raise InvalidSkillContextError(
                "Skill workspace must be an existing directory."
            )

        unit_id = str(unit_id).strip()
        if not unit_id or _contains_control_character(unit_id):
            raise InvalidSkillContextError(
                "Skill unit_id must be a non-empty single-line value."
            )

        checkpoint = str(checkpoint or "").strip()
        if _contains_control_character(checkpoint):
            raise InvalidSkillContextError(
                "Skill checkpoint must be a single-line value."
            )

        object.__setattr__(self, "workspace", workspace_path)
        object.__setattr__(self, "unit_id", unit_id)
        object.__setattr__(self, "checkpoint", checkpoint)
        object.__setattr__(
            self, "inputs", _normalize_paths(workspace_path, inputs, kind="input")
        )
        object.__setattr__(
            self, "outputs", _normalize_paths(workspace_path, outputs, kind="output")
        )

    @property
    def input_paths(self) -> tuple[Path, ...]:
        """Resolve inputs inside the Workspace, rechecking symlink safety."""

        return tuple(self.resolve(path) for path in self.inputs)

    @property
    def output_paths(self) -> tuple[Path, ...]:
        """Resolve outputs inside the Workspace, rechecking symlink safety."""

        return tuple(self.resolve(path) for path in self.outputs)

    def resolve(self, relative_path: str | os.PathLike[str]) -> Path:
        """Resolve one path inside this context's Workspace.

        This is the only path-joining operation in the public interface.  It is
        also safe to call after context construction because it re-evaluates
        symlinks before returning an absolute path.
        """

        relative = _normalize_path(self.workspace, relative_path, kind="artifact")
        return _resolve_inside_workspace(self.workspace, relative, kind="artifact")

    def _revalidate(self) -> None:
        for path in (*self.inputs, *self.outputs):
            _resolve_inside_workspace(self.workspace, path, kind="artifact")


@dataclass(frozen=True, slots=True)
class SkillResult:
    """Observable result of a successful adapter invocation."""

    adapter: str
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: float

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True, slots=True)
class SkillProcessOwner:
    """Minimal local-process identity safe to persist outside Run state."""

    adapter: str
    pid: int
    process_group_id: int
    start_token: str

    def __post_init__(self) -> None:
        if not self.adapter or _contains_control_character(self.adapter):
            raise ValueError("owner adapter must be a non-empty single-line value")
        if self.pid <= 0 or self.process_group_id <= 0:
            raise ValueError("owner process identities must be positive")
        if not re.fullmatch(r"[0-9a-f]{64}", self.start_token):
            raise ValueError("owner start_token must be a SHA-256 digest")

    def is_live(self) -> bool:
        try:
            current_group = os.getpgid(self.pid)
        except OSError:
            return False
        if current_group != self.process_group_id:
            return False
        current_token = _process_start_token(self.pid)
        if current_token != self.start_token:
            return False
        try:
            os.killpg(self.process_group_id, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


@runtime_checkable
class SkillExecutionHandle(Protocol):
    """Bounded lifecycle interface for one already-started Skill execution."""

    @property
    def owner(self) -> SkillProcessOwner: ...

    def is_alive(self) -> bool: ...

    def release(self) -> None: ...

    def wait(self) -> SkillResult: ...

    def terminate(self) -> None: ...


@runtime_checkable
class SkillAdapter(Protocol):
    """Adapter seam for running one Skill invocation."""

    @property
    def adapter(self) -> str:
        """Stable diagnostic identifier; never a raw command."""

        ...

    def run(self, context: SkillContext) -> SkillResult:
        """Run the Skill or raise a typed ``SkillExecutionError``."""

        ...


@runtime_checkable
class LifecycleSkillAdapter(SkillAdapter, Protocol):
    """Skill adapter that exposes process ownership before blocking for result."""

    def start(self, context: SkillContext) -> SkillExecutionHandle: ...


@dataclass(slots=True)
class SubprocessSkillExecution:
    """Lifecycle handle that never exposes command arguments or environment."""

    owner: SkillProcessOwner
    _process: subprocess.Popen[str] = field(repr=False)
    _started: float = field(repr=False)
    _timeout_seconds: float | None = field(repr=False)
    _gate_descriptor: int | None = field(repr=False)
    _result: SkillResult | None = field(default=None, init=False, repr=False)
    _error: SkillExecutionError | None = field(default=None, init=False, repr=False)

    def is_alive(self) -> bool:
        return self._process.poll() is None

    def release(self) -> None:
        descriptor = self._gate_descriptor
        if descriptor is None:
            return
        self._gate_descriptor = None
        try:
            os.write(descriptor, b"1")
        except OSError as exc:
            raise SkillLaunchError(
                f"Skill adapter '{self.owner.adapter}' start gate could not be released.",
                adapter=self.owner.adapter,
                stdout="",
                stderr="",
                elapsed_ms=_elapsed_ms(self._started),
                exit_code=None,
            ) from exc
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass

    def wait(self) -> SkillResult:
        if self._result is not None:
            return self._result
        if self._error is not None:
            raise self._error
        self.release()
        try:
            stdout, stderr = self._process.communicate(timeout=self._timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            self.terminate()
            try:
                stdout, stderr = self._process.communicate()
            except OSError:
                stdout, stderr = _text_output(exc.stdout), _text_output(exc.stderr)
            self._error = SkillTimeoutError(
                f"Skill adapter '{self.owner.adapter}' timed out.",
                adapter=self.owner.adapter,
                stdout=stdout or _text_output(exc.stdout),
                stderr=stderr or _text_output(exc.stderr),
                elapsed_ms=_elapsed_ms(self._started),
                exit_code=None,
            )
            raise self._error from None

        self._result = SkillResult(
            adapter=self.owner.adapter,
            exit_code=int(self._process.returncode),
            stdout=stdout or "",
            stderr=stderr or "",
            elapsed_ms=_elapsed_ms(self._started),
        )
        if not self._result.succeeded:
            self._error = SkillProcessError(
                f"Skill adapter '{self.owner.adapter}' exited with code "
                f"{self._result.exit_code}.",
                adapter=self._result.adapter,
                stdout=self._result.stdout,
                stderr=self._result.stderr,
                elapsed_ms=self._result.elapsed_ms,
                exit_code=self._result.exit_code,
            )
            raise self._error
        return self._result

    def terminate(self) -> None:
        descriptor = self._gate_descriptor
        self._gate_descriptor = None
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if not self.is_alive():
            return
        _signal_process_group(
            self._process, self.owner.process_group_id, signal.SIGTERM
        )
        try:
            self._process.wait(timeout=_TERMINATION_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        if _process_group_is_live(self.owner.process_group_id):
            _signal_process_group(
                self._process, self.owner.process_group_id, signal.SIGKILL
            )
        try:
            self._process.wait(timeout=_TERMINATION_GRACE_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            pass


@dataclass(frozen=True, slots=True)
class SubprocessSkillAdapter:
    """Run the repository's existing ``scripts/run.py`` protocol safely."""

    script_path: Path = field(repr=False)
    adapter: str = "subprocess"
    python_executable: str = field(default_factory=lambda: sys.executable, repr=False)
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        adapter = str(self.adapter or "").strip()
        if not adapter or _contains_control_character(adapter):
            raise ValueError("adapter must be a non-empty single-line identifier")
        timeout = self.timeout_seconds
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        object.__setattr__(
            self, "script_path", Path(self.script_path).expanduser().resolve()
        )
        object.__setattr__(self, "adapter", adapter)
        object.__setattr__(self, "python_executable", os.fspath(self.python_executable))

    @classmethod
    def for_repo_skill(
        cls,
        *,
        repo_root: Path,
        skill: str,
        python_executable: str | os.PathLike[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> SubprocessSkillAdapter:
        """Locate ``.codex/skills/<skill>/scripts/run.py`` without caller joins."""

        skill_name = str(skill or "").strip()
        if not _SKILL_NAME.fullmatch(skill_name):
            raise InvalidSkillAdapterError(
                "Skill must use a lowercase repository Skill name."
            )
        root = Path(repo_root).expanduser().resolve()
        script_path = root / ".codex" / "skills" / skill_name / "scripts" / "run.py"
        adapter = f"skill:{skill_name}:subprocess"
        resolved_script = script_path.resolve()
        try:
            resolved_script.relative_to(root)
        except ValueError:
            raise InvalidSkillAdapterError(
                "Repository Skill adapter must resolve inside repo_root."
            ) from None
        if not resolved_script.is_file():
            raise SkillAdapterNotFoundError(
                f"Skill adapter '{adapter}' is unavailable.",
                adapter=adapter,
                stdout="",
                stderr="",
                elapsed_ms=0.0,
                exit_code=None,
            )
        return cls(
            script_path=resolved_script,
            adapter=adapter,
            python_executable=os.fspath(python_executable or sys.executable),
            timeout_seconds=timeout_seconds,
        )

    def start(self, context: SkillContext) -> SubprocessSkillExecution:
        _require_context(context)
        context._revalidate()
        target_command = [
            self.python_executable,
            os.fspath(self.script_path),
            "--workspace",
            os.fspath(context.workspace),
            "--unit-id",
            context.unit_id,
            "--inputs",
            ";".join(path.as_posix() for path in context.inputs),
            "--outputs",
            ";".join(path.as_posix() for path in context.outputs),
            "--checkpoint",
            context.checkpoint,
        ]
        read_descriptor, write_descriptor = os.pipe()
        command = [
            self.python_executable,
            "-c",
            _PROCESS_GATE_BOOTSTRAP,
            str(read_descriptor),
            *target_command,
        ]
        started = time.perf_counter()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                pass_fds=(read_descriptor,),
            )
        except OSError:
            os.close(read_descriptor)
            os.close(write_descriptor)
            elapsed_ms = _elapsed_ms(started)
            raise SkillLaunchError(
                f"Skill adapter '{self.adapter}' could not be started.",
                adapter=self.adapter,
                stdout="",
                stderr="",
                elapsed_ms=elapsed_ms,
                exit_code=None,
            ) from None
        finally:
            try:
                os.close(read_descriptor)
            except OSError:
                pass
        start_token = _process_start_token(process.pid)
        if not start_token:
            try:
                os.close(write_descriptor)
            except OSError:
                pass
            _signal_process_group(process, process.pid, signal.SIGKILL)
            try:
                process.wait(timeout=_TERMINATION_GRACE_SECONDS)
            except (OSError, subprocess.TimeoutExpired):
                pass
            raise SkillLaunchError(
                f"Skill adapter '{self.adapter}' process identity could not be probed.",
                adapter=self.adapter,
                stdout="",
                stderr="",
                elapsed_ms=_elapsed_ms(started),
                exit_code=None,
            )
        return SubprocessSkillExecution(
            owner=SkillProcessOwner(
                adapter=self.adapter,
                pid=process.pid,
                process_group_id=process.pid,
                start_token=start_token,
            ),
            _process=process,
            _started=started,
            _timeout_seconds=self.timeout_seconds,
            _gate_descriptor=write_descriptor,
        )

    def run(self, context: SkillContext) -> SkillResult:
        return self.start(context).wait()


SkillHandler = Callable[[SkillContext], int | None]


@dataclass(frozen=True, slots=True)
class InMemorySkillAdapter:
    """Test/local adapter with the same observable contract as subprocesses.

    Handler writes to ``context.output_paths`` and returns an integer exit code
    (or ``None`` for success).  Printed stdout/stderr are captured in the result.
    """

    handler: SkillHandler = field(repr=False)
    adapter: str = "in-memory"

    def __post_init__(self) -> None:
        if not callable(self.handler):
            raise TypeError("handler must be callable")
        adapter = str(self.adapter or "").strip()
        if not adapter or _contains_control_character(adapter):
            raise ValueError("adapter must be a non-empty single-line identifier")
        object.__setattr__(self, "adapter", adapter)

    def run(self, context: SkillContext) -> SkillResult:
        _require_context(context)
        context._revalidate()
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        started = time.perf_counter()
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                returned = self.handler(context)
        except Exception as exc:
            raise SkillHandlerError(
                f"Skill adapter '{self.adapter}' handler raised {type(exc).__name__}.",
                adapter=self.adapter,
                stdout=stdout_buffer.getvalue(),
                stderr=stderr_buffer.getvalue(),
                elapsed_ms=_elapsed_ms(started),
                exit_code=None,
            ) from None

        if returned is None:
            exit_code = 0
        elif isinstance(returned, int) and not isinstance(returned, bool):
            exit_code = returned
        else:
            raise SkillHandlerError(
                f"Skill adapter '{self.adapter}' handler returned an invalid exit code.",
                adapter=self.adapter,
                stdout=stdout_buffer.getvalue(),
                stderr=stderr_buffer.getvalue(),
                elapsed_ms=_elapsed_ms(started),
                exit_code=None,
            )

        result = SkillResult(
            adapter=self.adapter,
            exit_code=exit_code,
            stdout=stdout_buffer.getvalue(),
            stderr=stderr_buffer.getvalue(),
            elapsed_ms=_elapsed_ms(started),
        )
        if not result.succeeded:
            raise SkillProcessError(
                f"Skill adapter '{self.adapter}' exited with code {result.exit_code}.",
                adapter=result.adapter,
                stdout=result.stdout,
                stderr=result.stderr,
                elapsed_ms=result.elapsed_ms,
                exit_code=result.exit_code,
            )
        return result


def _require_context(context: SkillContext) -> None:
    if not isinstance(context, SkillContext):
        raise TypeError("context must be a SkillContext")


def _normalize_paths(
    workspace: Path,
    paths: Iterable[str | os.PathLike[str]],
    *,
    kind: str,
) -> tuple[PurePosixPath, ...]:
    if isinstance(paths, (str, bytes, PurePath)):
        raise InvalidSkillContextError(
            f"Skill {kind}s must be an iterable of relative paths."
        )
    try:
        return tuple(_normalize_path(workspace, path, kind=kind) for path in paths)
    except TypeError as exc:
        raise InvalidSkillContextError(
            f"Skill {kind}s must be an iterable of relative paths."
        ) from exc


def _normalize_path(
    workspace: Path,
    raw_path: str | os.PathLike[str],
    *,
    kind: str,
) -> PurePosixPath:
    try:
        text = os.fspath(raw_path)
    except TypeError as exc:
        raise InvalidSkillPathError(f"Skill {kind} path must be path-like.") from exc
    if isinstance(text, bytes):
        raise InvalidSkillPathError(f"Skill {kind} path must be text.")
    if not text or text == "." or text.startswith("?"):
        raise InvalidSkillPathError(
            f"Skill {kind} path must name a Workspace artifact."
        )
    if "\\" in text or ";" in text or _contains_control_character(text):
        raise InvalidSkillPathError(f"Skill {kind} path is not portable or CLI-safe.")
    if text.endswith("/") and kind != "input":
        raise InvalidSkillPathError(
            f"Skill {kind} path must not end with a directory slash."
        )

    relative = PurePosixPath(text)
    windows_path = PureWindowsPath(text)
    raw_parts = text.split("/")
    if relative.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise InvalidSkillPathError(
            f"Skill {kind} path must be relative to the Workspace."
        )
    if any(part in {".", ".."} for part in raw_parts):
        raise InvalidSkillPathError(
            f"Skill {kind} path cannot contain traversal segments."
        )
    _resolve_inside_workspace(workspace, relative, kind=kind)
    return relative


def _resolve_inside_workspace(
    workspace: Path, relative: PurePosixPath, *, kind: str
) -> Path:
    candidate = (workspace / Path(*relative.parts)).resolve(strict=False)
    try:
        candidate.relative_to(workspace)
    except ValueError:
        raise InvalidSkillPathError(
            f"Skill {kind} path resolves outside the Workspace."
        ) from None
    return candidate


def _contains_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _elapsed_ms(started: float) -> float:
    return max(0.0, (time.perf_counter() - started) * 1000.0)


def _signal_process_group(
    process: subprocess.Popen[str], process_group_id: int, signal_number: int
) -> None:
    try:
        os.killpg(process_group_id, signal_number)
        return
    except (OSError, ProcessLookupError):
        pass
    try:
        if signal_number == signal.SIGKILL:
            process.kill()
        else:
            process.terminate()
    except OSError:
        pass


def _process_group_is_live(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _process_start_token(pid: int) -> str:
    try:
        completed = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    started = (completed.stdout or "").strip()
    if completed.returncode != 0 or not started:
        return ""
    material = f"{pid}:{started}".encode("utf-8", errors="replace")
    return hashlib.sha256(material).hexdigest()


def _text_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
