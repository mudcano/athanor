import sys
import asyncio


class TaskMaster:

    def __init__(self, *args, **kwargs):
        # queue-relevant data
        self._queue = None
        self._task = None
        self._running: bool = False

    def start(self):
        if not self._running:
            self._running = True
            self._queue = asyncio.PriorityQueue()
            self._task = asyncio.create_task(self.run())

    def stop(self):
        if self._running:
            self._queue.put_nowait((sys.maxsize, None))

    async def run(self):
        await self.on_start()
        while True:
            priority, task = await self._queue.get()
            if task is None:
                self._running = False
                break
            await self.run_task(task)
        await self.on_stop()
        self._task.cancel()
        self._queue = None

    async def run_task(self, task):
        pass

    async def on_start(self):
        pass

    async def on_stop(self):
        pass
