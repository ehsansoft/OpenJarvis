"""Task execution always uses the one server-owned scheduler."""

import asyncio
import threading

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/v1/scheduler")


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: str, request: Request):
    scheduler = request.app.state.task_scheduler
    if scheduler is None:
        raise HTTPException(409, "Restart the server with --scheduler")
    state = request.app.state
    loop = asyncio.get_running_loop()
    completion = loop.create_future()

    def deliver(result=None, error=None):
        if not completion.done():
            if error is not None:
                completion.set_exception(error)
            else:
                completion.set_result(result)

    def execute():
        worker = threading.current_thread()
        try:
            scheduler.run_task(task_id)
            with scheduler._lock:
                result = scheduler._store.get_run_logs(task_id, limit=1)[0]
            loop.call_soon_threadsafe(deliver, result)
        except KeyError:
            loop.call_soon_threadsafe(
                deliver, None, HTTPException(404, "Task not found")
            )
        except ValueError as exc:
            loop.call_soon_threadsafe(deliver, None, HTTPException(409, str(exc)))
        except Exception as exc:
            loop.call_soon_threadsafe(deliver, None, exc)
        finally:
            with state._managed_worker_lock:
                state._managed_workers.discard(worker)

    # Register a finite-lived worker, rather than the loop's persistent thread
    # pool thread: shutdown must wait for work, not for an idle pool to exit.
    worker = threading.Thread(target=execute, name="jarvis-task-run", daemon=True)
    with state._managed_worker_lock:
        if state._managed_runtime_stopping:
            raise HTTPException(503, "Runtime is stopping")
        state._managed_workers.add(worker)
        try:
            worker.start()
        except Exception:
            state._managed_workers.discard(worker)
            raise
    return await completion
