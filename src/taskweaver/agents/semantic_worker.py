"""Cancellable ownership of the optional synchronous Mem0 SDK for async chat.

Only JSON RPC crosses the private pipes. The child owns all SDK clients and store
locks; the parent owns the response reader and the short-lived local-work executor.
CLI callers continue using the native synchronous backend directly.
"""

import asyncio
import builtins
import json
import os
import sys
from asyncio import subprocess
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import redirect_stdout, suppress
from contextvars import copy_context
from typing import TYPE_CHECKING, cast

from ..config import Config

if TYPE_CHECKING:
    from .memory import SemanticBackend

_STOP_TIMEOUT = 0.75


class SemanticWorkerError(Exception):
    """An SDK programming error that must not become a tolerant provider failure."""


def _remote_error(response: dict[str, object]) -> Exception:
    name = str(response["error"])
    message = f"Semantic worker operation failed ({name})."
    if response.get("operational"):
        return OSError(message)
    error_type = getattr(builtins, name, None)
    if isinstance(error_type, type) and issubclass(error_type, Exception):
        return error_type(message)
    return SemanticWorkerError(message)


class SemanticWorker:
    """Synchronous SemanticBackend proxy serviced by an owned async subprocess.

    Backend methods must run outside the owning event loop. Cancellation terminates
    SDK work instead of leaving a network call running in an executor thread.
    """

    def __init__(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._process: subprocess.Process | None = None
        self._reader: asyncio.Task[None] | None = None
        self._pending: dict[int, asyncio.Future[object]] = {}
        self._next_id = 0
        self._closing = False
        self._close_task: asyncio.Task[None] | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._jobs: set[Future[object]] = set()

    @classmethod
    async def open(cls, config: Config) -> "SemanticWorker":
        """Start the SDK in a fresh interpreter, cleaning up even interrupted startup."""
        worker = cls()
        environment = os.environ | {"MEM0_TELEMETRY": "False"}
        spawn = asyncio.create_task(
            asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                __name__,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
            )
        )
        try:
            worker._process = await asyncio.shield(spawn)
            worker._reader = asyncio.create_task(worker._read_responses())
            await worker._request("open", config.model_dump(mode="json"))
            return worker
        except BaseException:
            # Shielding creation ensures even repeated cancellation leaves an owner.
            while not spawn.done():
                with suppress(asyncio.CancelledError):
                    await asyncio.shield(spawn)
            if not spawn.cancelled() and spawn.exception() is None:
                worker._process = spawn.result()
                await worker.close()
            raise

    async def run[T](self, operation: Callable[[], T]) -> T:
        """Offload only local operations that may wait on this process's RPC."""
        if self._closing:
            raise OSError("Semantic worker is closed.")
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="taskweaver-semantic")
        job = self._executor.submit(copy_context().run, operation)
        self._jobs.add(cast("Future[object]", job))
        try:
            return await asyncio.wrap_future(job)
        finally:
            if job.done():
                self._jobs.discard(cast("Future[object]", job))

    async def _request(self, operation: str, arguments: dict[str, object]) -> object:
        if (self._closing and operation != "close") or self._process is None or self._process.returncode is not None:
            raise OSError("Semantic worker is unavailable.")
        self._next_id += 1
        identifier = self._next_id
        response = self._loop.create_future()
        self._pending[identifier] = response
        try:
            stream = self._process.stdin
            if stream is None:
                raise OSError("Semantic worker input is unavailable.")
            payload = json.dumps({"id": identifier, "operation": operation, "arguments": arguments}).encode()
            # A length-prefixed JSON frame supports large get_all replies without
            # StreamReader.readline's fixed line-size limit.
            stream.write(len(payload).to_bytes(4, "big") + payload)
            await stream.drain()
            return await response
        finally:
            self._pending.pop(identifier, None)
            if response.done() and not response.cancelled():
                response.exception()
            elif not response.done():
                response.cancel()

    async def _read_responses(self) -> None:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("Semantic worker response reader has no output stream.")
        stream = self._process.stdout
        try:
            while True:
                size = int.from_bytes(await stream.readexactly(4), "big")
                response = json.loads(await stream.readexactly(size))
                pending = self._pending.get(response["id"])
                if pending is not None and not pending.done():
                    if "error" in response:
                        pending.set_exception(_remote_error(response))
                    else:
                        pending.set_result(response["result"])
        except (asyncio.IncompleteReadError, OSError):
            self._fail_pending(OSError("Semantic worker stopped before replying."))
        except Exception as exc:
            self._fail_pending(SemanticWorkerError(f"Semantic worker protocol failed ({type(exc).__name__})."))
            raise

    def _fail_pending(self, error: Exception) -> None:
        for pending in self._pending.values():
            if not pending.done():
                pending.set_exception(error)

    def _call(self, operation: str, arguments: dict[str, object]) -> object:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is self._loop:
            raise RuntimeError("Semantic worker calls must run outside the owning event loop.")
        return asyncio.run_coroutine_threadsafe(self._request(operation, arguments), self._loop).result()

    def add(self, value: str, *, user_id: str, metadata: dict[str, object], infer: bool) -> object:
        """Index an explicit fact in the child without inferring additional facts."""
        return self._call("add", {"value": value, "user_id": user_id, "metadata": metadata, "infer": infer})

    def delete(self, identifier: str) -> object:
        """Delete one semantic record in the child."""
        return self._call("delete", {"identifier": identifier})

    def get_all(self, *, user_id: str) -> object:
        """Read one user's provider records in the child."""
        return self._call("get_all", {"user_id": user_id})

    def search(self, query: str, *, user_id: str, limit: int) -> object:
        """Search one user's semantic records in the child."""
        return self._call("search", {"query": query, "user_id": user_id, "limit": limit})

    async def close(self) -> None:
        """Reap the process, unblock every RPC and join the drained local executor."""
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        interrupted = False
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError:
                interrupted = True
        self._close_task.result()
        if interrupted:
            raise asyncio.CancelledError

    async def _reap_process(self, process: subprocess.Process, *, active_requests: bool) -> None:
        """Close pipes and reap the child, escalating only when it cannot finish."""
        if process.stdin is not None:
            process.stdin.close()
        if active_requests and process.returncode is None:
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
            with suppress(BrokenPipeError, ConnectionResetError):
                await process.stdin.wait_closed()

    async def _drain_local_work(self) -> None:
        """Join local work only after every provider RPC has been unblocked."""
        if self._jobs:
            await asyncio.gather(*(asyncio.wrap_future(job) for job in self._jobs), return_exceptions=True)
            self._jobs.clear()
        if self._executor is not None:
            # All jobs have finished: joining cannot wait on a provider request.
            self._executor.shutdown(wait=True, cancel_futures=True)

    async def _close(self) -> None:
        self._closing = True
        process = self._process
        active_requests = bool(self._pending)
        cleanup_error = None
        if not active_requests and process is not None and process.returncode is None:
            try:
                await asyncio.wait_for(self._request("close", {}), _STOP_TIMEOUT)
            except TimeoutError:
                active_requests = True
            except Exception as exc:  # noqa: BLE001 - reap resources before propagating cleanup errors
                cleanup_error = exc
        self._fail_pending(OSError("Semantic worker closed."))
        try:
            if process is not None:
                await self._reap_process(process, active_requests=active_requests)
        finally:
            try:
                if self._reader is not None:
                    await self._reader
            finally:
                await self._drain_local_work()
        if cleanup_error is not None:
            raise cleanup_error


def _backend_operation(backend: object, operation: str, arguments: dict[str, object]) -> object:
    """Dispatch SDK calls without converting programming errors to provider failures."""
    sdk = cast("SemanticBackend", backend)
    if operation == "add":
        return sdk.add(
            cast("str", arguments["value"]),
            user_id=cast("str", arguments["user_id"]),
            metadata=cast("dict[str, object]", arguments["metadata"]),
            infer=cast("bool", arguments["infer"]),
        )
    if operation == "delete":
        return sdk.delete(cast("str", arguments["identifier"]))
    if operation == "get_all":
        return sdk.get_all(user_id=cast("str", arguments["user_id"]))
    if operation == "search":
        return sdk.search(
            cast("str", arguments["query"]),
            user_id=cast("str", arguments["user_id"]),
            limit=cast("int", arguments["limit"]),
        )
    raise ValueError("Unknown semantic worker operation.")


def _serve() -> None:
    """Child entrypoint; SDK stdout/stderr cannot enter RPC or private logs."""
    from ..database.connection import close_mem0_memory, mem0_memory  # noqa: PLC0415
    from .memory import BACKEND_OPERATION_ERRORS  # noqa: PLC0415

    output = sys.stdout.buffer
    source = sys.stdin.buffer
    backend = None
    with redirect_stdout(sys.stderr):
        try:
            while header := source.read(4):
                size = int.from_bytes(header, "big")
                request = json.loads(source.read(size))
                arguments = request["arguments"]
                response: dict[str, object] = {"id": request["id"]}
                try:
                    operation = request["operation"]
                    if operation == "open":
                        backend = mem0_memory(Config.model_validate(arguments))
                        result = None
                    elif operation == "close":
                        closing_backend, backend = backend, None
                        if closing_backend is not None:
                            close_mem0_memory(closing_backend)
                        result = None
                    elif backend is None:
                        raise RuntimeError("Semantic worker has not started.")
                    else:
                        result = _backend_operation(backend, operation, arguments)
                    response["result"] = result
                    payload = json.dumps(response).encode()
                except Exception as exc:  # noqa: BLE001 - RPC preserves programming errors as errors
                    # Exception messages/tracebacks may include private inputs or
                    # credentials. Only the class and operational classification cross.
                    response = {
                        "id": request["id"],
                        "error": type(exc).__name__,
                        "operational": isinstance(exc, BACKEND_OPERATION_ERRORS),
                    }
                    payload = json.dumps(response).encode()
                output.write(len(payload).to_bytes(4, "big") + payload)
                output.flush()
                if operation == "close":
                    break
        finally:
            if backend is not None:
                close_mem0_memory(backend)


if __name__ == "__main__":
    _serve()
