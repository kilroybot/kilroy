import asyncio
import json
from asyncio import Lock, Queue, Task
from json import JSONDecodeError
from typing import Optional, Tuple
from uuid import UUID

from kilroylib.utils import background
from pydantic import ValidationError

from kilroy.api.messages import (
    CreateMessage,
    DestroyMessage,
    ErrorMessage,
    GetStateMessage,
    IncomingMessage,
    StartMessage,
    StartOfflineMessage,
    StartOnlineMessage,
    StateChangeMessage,
    StateMessage,
    StopMessage,
    StopOfflineMessage,
    StopOnlineMessage,
)
from kilroy.config import Config
from kilroy.factories import RunnerFactory
from kilroy.runner import Runner
from kilroy.server import Controller


class APIController(Controller):
    _runner: Optional[Runner]
    _config: Optional[Config]
    _lock: Optional[Lock]
    _directs: Optional[Queue[Tuple[UUID, str]]]
    _broadcasts: Optional[Queue[str]]
    _polling_task: Optional[Task]

    def __init__(self) -> None:
        super().__init__()
        self._runner = None
        self._config = None
        self._lock = None
        self._directs = None
        self._broadcasts = None
        self._polling_task = None

    async def _poll_runner(self) -> None:
        while True:
            message = await background(self._runner.poll)
            await self._broadcasts.put(message)

    async def init(self) -> None:
        self._lock = Lock()
        self._directs = Queue()
        self._broadcasts = Queue()

    async def cleanup(self) -> None:
        if self._polling_task is not None:
            self._polling_task.cancel()

    async def _send_direct_message(self, sender: UUID, message: str) -> None:
        await self._directs.put((sender, message))

    async def _handle_error(
        self, sender: UUID, message: str, reason: str
    ) -> None:
        try:
            message_id = json.loads(message)["id"]
        except (JSONDecodeError, KeyError):
            message_id = None

        reply = ErrorMessage(response_to=message_id, message=reason)
        await self._send_direct_message(sender, reply.json())

    async def _handle_get_state(
        self, sender: UUID, message: GetStateMessage
    ) -> None:
        async with self._lock:
            is_created = self._runner is not None
            is_running = self._runner.is_running() if is_created else False
            is_offline_training = (
                self._runner.is_offline_training() if is_created else False
            )
            is_online_training = (
                self._runner.is_online_training() if is_created else False
            )
            config = self._config

        reply = StateMessage(
            created=is_created,
            running=is_running,
            offline_training=is_offline_training,
            online_training=is_online_training,
            config=config,
        )

        await self._send_direct_message(sender, reply.json())

    async def _handle_create(
        self, sender: UUID, message: CreateMessage
    ) -> None:
        try:
            if self._runner is not None:
                raise RuntimeError("Run already created.")
            self._runner = RunnerFactory.create(message.config)
            self._config = message.config
            self._polling_task = asyncio.create_task(self._poll_runner())
            await self._send_direct_message(
                sender,
                StateChangeMessage(change="created").json(),
            )
        except (ValidationError, RuntimeError) as e:
            await self._handle_error(sender, message.json(), str(e))

    async def _handle_destroy(
        self, sender: UUID, message: DestroyMessage
    ) -> None:
        try:
            if self._runner is None:
                raise RuntimeError("Run not created.")
            self._runner = None
            self._config = None
            self._polling_task = None
            await self._send_direct_message(
                sender,
                StateChangeMessage(change="destroyed").json(),
            )
        except RuntimeError as e:
            await self._handle_error(sender, message.json(), str(e))

    async def _handle_start(self, sender: UUID, message: StartMessage) -> None:
        try:
            if self._runner is None:
                raise RuntimeError("Run not created.")
            if self._runner.is_running():
                raise RuntimeError("Run is already running.")
            self._runner.start()
        except RuntimeError as e:
            await self._handle_error(sender, message.json(), str(e))

    async def _handle_start_offline(
        self, sender: UUID, message: StartOfflineMessage
    ) -> None:
        try:
            if self._runner is None:
                raise RuntimeError("Run not created.")
            if self._runner.is_offline_training():
                raise RuntimeError("Offline training is already running.")
            self._runner.start_offline_training()
        except RuntimeError as e:
            await self._handle_error(sender, message.json(), str(e))

    async def _handle_stop_offline(
        self, sender: UUID, message: StopOfflineMessage
    ) -> None:
        try:
            if self._runner is None:
                raise RuntimeError("Run not created.")
            if not self._runner.is_offline_training():
                raise RuntimeError("Offline training is not running.")
            self._runner.stop_offline_training()
        except RuntimeError as e:
            await self._handle_error(sender, message.json(), str(e))

    async def _handle_start_online(
        self, sender: UUID, message: StartOnlineMessage
    ) -> None:
        try:
            if self._runner is None:
                raise RuntimeError("Run not created.")
            if self._runner.is_online_training():
                raise RuntimeError("Online training is already running.")
            self._runner.start_online_training()
        except RuntimeError as e:
            await self._handle_error(sender, message.json(), str(e))

    async def _handle_stop_online(
        self, sender: UUID, message: StopOnlineMessage
    ) -> None:
        try:
            if self._runner is None:
                raise RuntimeError("Run not created.")
            if not self._runner.is_online_training():
                raise RuntimeError("Online training is not running.")
            self._runner.stop_online_training()
        except RuntimeError as e:
            await self._handle_error(sender, message.json(), str(e))

    async def _handle_stop(self, sender: UUID, message: StopMessage) -> None:
        try:
            if self._runner is None:
                raise RuntimeError("Run not created.")
            if not self._runner.is_running():
                raise RuntimeError("Run is not running.")
            self._runner.stop()
        except RuntimeError as e:
            await self._handle_error(sender, message.json(), str(e))

    async def handle_message(self, sender: UUID, message: str) -> None:
        try:
            parsed_message = IncomingMessage.parse_raw(message)
        except ValidationError as e:
            await self._handle_error(sender, message, str(e))
            return

        message_obj = parsed_message.__root__

        if isinstance(message_obj, GetStateMessage):
            await self._handle_get_state(sender, message_obj)
        elif isinstance(message_obj, CreateMessage):
            await self._handle_create(sender, message_obj)
        elif isinstance(message_obj, DestroyMessage):
            await self._handle_destroy(sender, message_obj)
        elif isinstance(message_obj, StartMessage):
            await self._handle_start(sender, message_obj)
        elif isinstance(message_obj, StartOfflineMessage):
            await self._handle_start_offline(sender, message_obj)
        elif isinstance(message_obj, StopOfflineMessage):
            await self._handle_stop_offline(sender, message_obj)
        elif isinstance(message_obj, StartOnlineMessage):
            await self._handle_start_online(sender, message_obj)
        elif isinstance(message_obj, StopOnlineMessage):
            await self._handle_stop_online(sender, message_obj)
        elif isinstance(message_obj, StopMessage):
            await self._handle_stop(sender, message_obj)
        else:
            await self._handle_error(sender, message, "Invalid message type.")

    async def poll_direct(self) -> Tuple[UUID, str]:
        return await self._directs.get()

    async def poll_broadcast(self) -> str:
        return await self._broadcasts.get()
