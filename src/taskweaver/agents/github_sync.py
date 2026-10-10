"""Read-only automatic GitHub imports in a cancellable, privately owned process."""

from __future__ import annotations

import asyncio
import json
import sys
from asyncio import subprocess
from collections.abc import Sequence
from contextlib import redirect_stdout, suppress
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from github import GithubException
from requests import RequestException

from .github_issues import GitHubIssueSyncService, SyncResult

_STOP_TIMEOUT = 0.75


class GitHubSyncError(RuntimeError):
    """An automatic sync worker failed without exposing remote content or secrets."""


def _decode_response(payload: bytes) -> SyncResult:
    try:
        response = json.loads(payload)
        if "error" in response:
            error = response["error"]
            status = error.get("status")
            if isinstance(status, int):
                hints = {
                    401: "Check your GitHub token.",
                    403: "Check repository access and GitHub API quota before retrying.",
                    404: "Check the configured repository and mapped issue access.",
                    429: "GitHub API quota is exhausted; retry later.",
                }
                hint = hints.get(status, "Retry later or check GitHub status.")
                message = f"GitHub sync failed (HTTP {status}). {hint}"
                raise GithubException(status, {"message": message})
            if error.get("kind") == "network":
                raise OSError("GitHub sync could not reach the API. Check connectivity and retry later.")
            if error.get("kind") == "validation":
                raise ValueError("GitHub sync request is invalid; configure repositories as owner/repo.")
            raise GitHubSyncError("GitHub sync worker failed; check the local database and installation.")
        result = response["result"]
        return SyncResult(
            imported=int(result["imported"]),
            updated=int(result["updated"]),
            pushed=int(result["pushed"]),
            unchanged=int(result["unchanged"]),
            conflicts=list(result["conflicts"]),
            task_ids=[UUID(identifier) for identifier in result["task_ids"]],
        )
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise GitHubSyncError("GitHub sync worker returned an invalid response.") from exc


async def _stop_process(process: subprocess.Process) -> None:
    if process.returncode is None:
        with suppress(ProcessLookupError):
            process.terminate()
    try:
        await asyncio.wait_for(process.wait(), _STOP_TIMEOUT)
    except TimeoutError:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
        await process.wait()
    if process.stdin is not None:
        process.stdin.close()
        with suppress(BrokenPipeError, ConnectionResetError):
            await process.stdin.wait_closed()


async def _finish_owned_task[T](task: asyncio.Task[T]) -> bool:
    """Drain ownership work despite repeated cancellation, recording interruptions."""
    interrupted = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            interrupted = True
    task.result()
    return interrupted


async def run_github_sync(db_path: Path, repos: Sequence[str]) -> SyncResult:
    """Import new open issues, then pull all mapped issues without any GitHub writes.

    Empty repository selections do not launch a process, open SQLite, or use the
    network. The child owns the synchronous SDK and all its sockets. Cancelling
    this coroutine terminates and reaps that child before cancellation returns.
    GitHub failures retain HTTP status but never remote response bodies or tokens.
    Counts reflect both passes; unchanged counts the final mapped pull, so a task
    imported or updated in the first pass can also be unchanged in the second.
    """
    names = list(repos)
    if not names:
        return SyncResult()
    request = json.dumps({"db_path": str(db_path), "repos": names}).encode()
    spawn = asyncio.create_task(
        asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            __name__,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    )
    try:
        process = await asyncio.shield(spawn)
        payload, _ = await process.communicate(request)
        if process.returncode != 0:
            raise GitHubSyncError("GitHub sync worker stopped before replying; check the local installation.")
        return _decode_response(payload)
    finally:
        interrupted = await _finish_owned_task(spawn)
        process = spawn.result()
        interrupted = await _finish_owned_task(asyncio.create_task(_stop_process(process))) or interrupted
        if interrupted:
            raise asyncio.CancelledError


def _serve() -> None:
    """One private JSON request/reply; no SDK output enters the response or logs."""
    source = sys.stdin.buffer
    output = sys.stdout.buffer
    with redirect_stdout(sys.stderr):
        try:
            request = json.loads(source.read())
            with GitHubIssueSyncService(Path(request["db_path"])) as service:
                imported = service.import_issues(request["repos"], state="open")
                synced = service.sync(request["repos"], push=False)
            result = SyncResult(
                imported=imported.imported,
                updated=imported.updated + synced.updated,
                pushed=0,
                # This counts the final mapped pull, including newly imported tasks.
                unchanged=synced.unchanged,
                conflicts=list(dict.fromkeys([*imported.conflicts, *synced.conflicts])),
                task_ids=list(dict.fromkeys([*imported.task_ids, *synced.task_ids])),
            )
            response = {"result": asdict(result)}
        except GithubException as exc:
            response = {"error": {"kind": "http", "status": exc.status}}
        except (RequestException, OSError):
            response = {"error": {"kind": "network"}}
        except ValueError:
            response = {"error": {"kind": "validation"}}
        except Exception:  # noqa: BLE001 - private worker protocol must never serialize exception bodies
            response = {"error": {"kind": "worker"}}
    output.write(json.dumps(response, default=str).encode())
    output.flush()


if __name__ == "__main__":
    _serve()
