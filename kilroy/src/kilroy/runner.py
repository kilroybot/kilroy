import asyncio
from asyncio import AbstractEventLoop
from concurrent.futures import Executor, ThreadPoolExecutor
from queue import Queue
from threading import Event, Lock
from typing import Awaitable, Optional

from kilroylib.training.offline.trainer import Trainer as OfflineTrainer
from kilroylib.training.online.trainer import Trainer as OnlineTrainer
from kilroyshare import Face, OfflineModule, OnlineModule

from kilroy.api.messages import (
    ErrorMessage,
    InfoMessage,
    StateChange,
    StateChangeMessage,
)
from kilroy.utils import noop


class GenericRunner:
    _commands: Optional[asyncio.Queue[Awaitable]]
    _messages: Queue[str]
    _loop: Optional[AbstractEventLoop]
    _running: bool
    _stop_requested: bool
    _executor: Executor
    _thread_lock: Lock
    _ended: Event

    def __init__(self) -> None:
        self._commands = None
        self._messages = Queue()
        self._loop = None
        self._running = False
        self._stop_requested = False
        self._executor = ThreadPoolExecutor()
        self._thread_lock = Lock()
        self._ended = Event()

    def _should_stop(self) -> bool:
        with self._thread_lock:
            return self._stop_requested

    def _report_info(self, message: str) -> None:
        message = InfoMessage(message=message)
        self._messages.put(message.json())

    def _report_error(self, message: str) -> None:
        message = ErrorMessage(message=message)
        self._messages.put(message.json())

    async def _init(self) -> None:
        pass

    async def _cleanup(self) -> None:
        pass

    async def _format_exception(self, e: Exception) -> str:
        return str(e)

    async def _main(self) -> None:
        await self._init()
        while not self._should_stop():
            command = await self._commands.get()
            try:
                await command
            except Exception as e:
                self._report_error(await self._format_exception(e))
            await noop()
        await self._cleanup()

    def _schedule(self, a: Awaitable) -> None:
        asyncio.run_coroutine_threadsafe(a, self._loop)

    def _send_command(self, command: Awaitable) -> None:
        with self._thread_lock:
            if not self._running:
                raise RuntimeError("Runner not started.")
            if self._stop_requested:
                raise RuntimeError("Runner is stopping.")

            async def add_command(command: Awaitable) -> None:
                await self._commands.put(command)

            self._schedule(add_command(command))

    def _bump(self) -> None:
        async def add_noop() -> None:
            await self._commands.put(noop())

        self._schedule(add_noop())

    def start(self) -> None:
        def setup() -> None:
            try:
                with self._thread_lock:
                    self._loop = asyncio.new_event_loop()
                    self._commands = asyncio.Queue(loop=self._loop)
                    self._running = True
                    self._ended.clear()
                self._loop.run_until_complete(self._main())
            finally:
                with self._thread_lock:
                    self._running = False
                    self._commands = None
                    self._messages = []
                    self._loop = None
                    self._stop_requested = False
                    self._ended.set()

        self._executor.submit(setup)

    def stop(self) -> None:
        with self._thread_lock:
            self._stop_requested = True
            self._bump()

    def is_running(self) -> bool:
        with self._thread_lock:
            return self._running

    def poll(self) -> str:
        return self._messages.get()

    def wait(self) -> None:
        self._ended.wait()


class Runner(GenericRunner):
    _offline_training: bool
    _online_training: bool

    def __init__(
        self,
        face: Face,
        offline_module: OfflineModule,
        offline_trainer: OfflineTrainer,
        online_module: OnlineModule,
        online_trainer: OnlineTrainer,
    ) -> None:
        super().__init__()
        self.face = face
        self.offline_module = offline_module
        self.offline_trainer = offline_trainer
        self.online_module = online_module
        self.online_trainer = online_trainer
        self._offline_training = False
        self._online_training = False

    def _report_state_change(self, change: StateChange) -> None:
        message = StateChangeMessage(change=change)
        self._messages.put(message.json())

    async def _init(self) -> None:
        async def command() -> None:
            await self.face.init()
            await self.offline_trainer.init()
            await self.online_trainer.init()
            self._report_state_change("started")

        self._send_command(command())

    async def _cleanup(self) -> None:
        await self.face.cleanup()
        self._report_state_change("stopped")

    def start_offline_training(self) -> None:
        async def command() -> None:
            async def train() -> None:
                self._report_state_change("started_offline")
                with self._thread_lock:
                    self._offline_training = True
                await self.offline_trainer.start(
                    self.offline_module, self.face
                )
                with self._thread_lock:
                    self._offline_training = False
                self._report_state_change("stopped_offline")

            asyncio.create_task(train())

        self._send_command(command())

    def stop_offline_training(self) -> None:
        async def command() -> None:
            self._report_info("Stopping offline training...")
            await self.offline_trainer.stop()

        self._send_command(command())

    def start_online_training(self) -> None:
        async def command() -> None:
            async def train() -> None:
                self._report_state_change("started_online")
                with self._thread_lock:
                    self._online_training = False
                await self.online_trainer.start(self.online_module, self.face)
                with self._thread_lock:
                    self._online_training = False
                self._report_state_change("stopped_offline")

            asyncio.create_task(train())

        self._send_command(command())

    def stop_online_training(self) -> None:
        async def command() -> None:
            self._report_info("Stopping online training...")
            await self.online_trainer.stop()

        self._send_command(command())

    def is_offline_training(self) -> bool:
        with self._thread_lock:
            return self._offline_training

    def is_online_training(self) -> bool:
        with self._thread_lock:
            return self._online_training
