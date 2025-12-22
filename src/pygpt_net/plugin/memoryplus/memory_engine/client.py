import atexit
import queue
import threading
import time
from multiprocessing import Queue
from typing import Callable, Dict, Any, Optional

from .protocol import (
    ENGINE_MODES,
    REQUEST_FORGET,
    REQUEST_HEALTH,
    REQUEST_INGEST,
    REQUEST_SEARCH,
    REQUEST_SYNTH,
    REQUEST_SHUTDOWN,
    EngineRequest,
)
from .worker import MemoryWorker


class MemoryEngineClient:
    def __init__(
        self,
        config_builder: Callable[[], Dict[str, Any]],
        group_id_provider: Callable[[], str],
        logger: Optional[Callable[[str], None]] = None,
        error_logger: Optional[Callable[[str], None]] = None,
    ):
        self.config_builder = config_builder
        self.group_id_provider = group_id_provider
        self.logger = logger or (lambda msg: None)
        self.error_logger = error_logger or (lambda msg: None)
        self.request_queue: Queue = Queue()
        self.response_queue: Queue = Queue()
        self.worker: Optional[MemoryWorker] = None
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._worker_lock = threading.Lock()
        self.default_timeout = 30.0
        self.last_error: Optional[str] = None
        self.last_error_type: Optional[str] = None
        self._init_error: Optional[str] = None
        atexit.register(self.shutdown)

    def set_default_timeout(self, timeout: float):
        try:
            self.default_timeout = max(1.0, float(timeout))
        except Exception:
            self.default_timeout = 30.0

    def _log(self, msg: str):
        try:
            self.logger(msg)
        except Exception:
            pass

    def _set_error(self, msg: str, error_type: Optional[str] = None):
        self.last_error = msg
        self.last_error_type = error_type

    def _error(self, msg: str, error_type: Optional[str] = None):
        self._set_error(msg, error_type)
        try:
            self.error_logger(msg)
        except Exception:
            pass

    def _start_worker(self) -> bool:
        with self._worker_lock:
            if self.worker and self.worker.is_alive():
                return True

            self._init_error = None
            self.last_error = None
            self.last_error_type = None
            config = self.config_builder()
            group_id = self.group_id_provider()
            self.worker = MemoryWorker(config=config, group_id=group_id, request_queue=self.request_queue, response_queue=self.response_queue)
            self.worker.start()
            return self.worker.is_alive()

    def restart(self) -> bool:
        self.shutdown()
        return self._start_worker()

    def start(self) -> bool:
        return self._start_worker()

    def shutdown(self):
        with self._worker_lock:
            worker = self.worker
            self.worker = None
        if not worker:
            return
        try:
            req = EngineRequest(operation=REQUEST_SHUTDOWN)
            self.request_queue.put(req.to_dict())
            worker.join(timeout=5)
        except Exception:
            pass
        finally:
            if worker and worker.is_alive():
                try:
                    worker.terminate()
                except Exception:
                    pass
            self._init_error = None

    def is_alive(self) -> bool:
        with self._worker_lock:
            return bool(self.worker and self.worker.is_alive())

    def _pop_pending(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._pending.pop(request_id, None)

    def _store_pending(self, request_id: str, payload: Dict[str, Any]):
        with self._lock:
            self._pending[request_id] = payload

    def _handle_system_response(self, resp: Dict[str, Any]) -> bool:
        if resp.get("request_id") != "init":
            return False
        status = resp.get("status")
        error = resp.get("error")
        if status == "error":
            self._init_error = error or "Graphiti worker failed to initialize."
            self._error(f"Graphiti worker init failed: {self._init_error}", error_type="init")
        else:
            self._init_error = None
        return True

    def _wait_for_response(self, request_id: str, timeout: float) -> Optional[Dict[str, Any]]:
        pending = self._pop_pending(request_id)
        if pending:
            return pending

        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                remaining = end_time - time.time()
                if remaining <= 0:
                    break
                resp = self.response_queue.get(timeout=remaining)
                if self._handle_system_response(resp):
                    if self._init_error:
                        return None
                    continue
                rid = resp.get("request_id")
                if rid == request_id:
                    return resp
                self._store_pending(rid, resp)
            except queue.Empty:
                break
            except Exception:
                break
        return None

    def _request(self, operation: str, payload: Dict[str, Any], timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        self.last_error = None
        self.last_error_type = None
        if not self._start_worker():
            self._error("Persistent worker is not available", error_type="worker_unavailable")
            return None

        request = EngineRequest(operation=operation, payload=payload)
        try:
            self.request_queue.put(request.to_dict())
        except Exception as e:
            self._error(f"Failed to enqueue request: {e}", error_type="enqueue_failed")
            return None

        wait_timeout = self.default_timeout if timeout is None else float(timeout)
        resp = self._wait_for_response(request.request_id, wait_timeout)
        if not resp:
            if self._init_error:
                return None
            self._error("Timed out waiting for engine response", error_type="timeout")
        return resp

    def health(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        return self._request(REQUEST_HEALTH, {}, timeout=timeout or 5.0)

    def ingest(self, name: str, content: str, mode: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        return self._request(REQUEST_INGEST, {"name": name, "content": content, "mode": mode}, timeout=timeout)

    def search(self, query: str, limit: int, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        return self._request(REQUEST_SEARCH, {"query": query, "limit": limit}, timeout=timeout)

    def forget(
        self,
        query: Optional[str] = None,
        episode_id: Optional[str] = None,
        name: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {}
        if query:
            payload["query"] = query
        if episode_id:
            payload["episode_id"] = episode_id
        if name:
            payload["name"] = name
        return self._request(REQUEST_FORGET, payload, timeout=timeout)

    def synthesize(self, content: str, mode: str = "Synthesizer", timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        return self._request(REQUEST_SYNTH, {"content": content, "mode": mode}, timeout=timeout)


__all__ = [
    "MemoryEngineClient",
    "ENGINE_MODES",
]
