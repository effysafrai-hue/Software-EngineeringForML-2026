import asyncio
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional
import logging

logger = logging.getLogger("chat_queue")


class Priority(IntEnum):
    INTERACTIVE_CHAT = 1      # User-facing real-time chat messages (highest priority)
    SHARED_CALENDAR_CHAT = 2  # Shared group calendar chat
    BACKGROUND_SUMMARY = 3    # Background notifications / summaries (lowest priority)


@dataclass(order=True)
class ChatJob:
    priority: int
    future: Any = field(compare=False)
    func: Callable = field(compare=False)
    args: tuple = field(compare=False)
    kwargs: dict = field(compare=False)


class ChatQueueManager:
    def __init__(self, max_workers: int = 4):
        self._queue: Optional[asyncio.PriorityQueue] = None
        self._workers: List[asyncio.Task] = []
        self._max_workers = max_workers
        self._running = False

    def _ensure_queue(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._queue is None:
            self._queue = asyncio.PriorityQueue()

    async def start(self):
        """Start worker pool."""
        if self._running:
            return
        self._queue = asyncio.PriorityQueue()
        self._running = True
        self._workers = []
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(f"worker-{i+1}"))
            self._workers.append(task)
        logger.info(f"ChatQueueManager started with {self._max_workers} worker tasks.")

    async def stop(self):
        """Gracefully stop worker pool."""
        if not self._running:
            return
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        self._queue = None
        logger.info("ChatQueueManager stopped.")

    async def submit(self, priority: Priority, func: Callable, *args, **kwargs) -> Any:
        """Submit a job to the priority queue and await its asynchronous completion."""
        self._ensure_queue()
        if not self._running:
            return await asyncio.to_thread(func, *args, **kwargs)

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        job = ChatJob(
            priority=int(priority),
            future=future,
            func=func,
            args=args,
            kwargs=kwargs,
        )
        await self._queue.put(job)
        return await future

    async def _worker(self, name: str):
        while self._running:
            try:
                job = await self._queue.get()
                try:
                    res = await asyncio.to_thread(job.func, *job.args, **job.kwargs)
                    if not job.future.done():
                        job.future.set_result(res)
                except Exception as ex:
                    if not job.future.done():
                        job.future.set_exception(ex)
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {name} error: {e}")


chat_queue = ChatQueueManager(max_workers=4)
