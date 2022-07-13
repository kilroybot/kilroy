import asyncio
from asyncio import Queue
from typing import Dict
from uuid import UUID, uuid4

import websockets

from kilroy.server.controller import Controller


class Server:
    _host: str
    _port: int
    _controller: Controller
    _connected: Dict[UUID, websockets.WebSocketServerProtocol]
    _queues: Dict[UUID, Queue]

    def __init__(
        self, port: int, controller: Controller, host: str = "localhost"
    ) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._controller = controller
        self._connected = {}
        self._queues = {}

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def _init(self) -> None:
        await self._controller.init()

    async def _cleanup(self) -> None:
        await self._controller.cleanup()

    async def _receive(
        self, uid: UUID, websocket: websockets.WebSocketServerProtocol
    ) -> None:
        try:
            async for message in websocket:
                await self._controller.handle_message(uid, message)
        except websockets.ConnectionClosedError:
            pass

    async def _send(
        self,
        websocket: websockets.WebSocketServerProtocol,
        queue: Queue,
    ) -> None:
        try:
            while True:
                message = await queue.get()
                await websocket.send(message)
        except websockets.ConnectionClosedError:
            pass

    async def _handle(
        self, websocket: websockets.WebSocketServerProtocol
    ) -> None:
        uid = uuid4()
        queue = Queue()
        self._connected[uid] = websocket
        self._queues[uid] = queue

        coroutines = [
            self._receive(uid, websocket),
            self._send(websocket, queue),
        ]
        done, pending = await asyncio.wait(
            [asyncio.create_task(coro) for coro in coroutines],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        self._connected.pop(uid)
        self._queues.pop(uid)

    async def _serve(self) -> websockets.WebSocketServer:
        return await websockets.serve(self._handle, self.host, self.port)

    async def _handle_directs(self) -> None:
        while True:
            uid, message = await self._controller.poll_direct()
            queue = self._queues.get(uid, None)
            if queue is not None:
                await queue.put(message)

    async def _handle_broadcasts(self) -> None:
        while True:
            message = await self._controller.poll_broadcast()
            for queue in self._queues.values():
                await queue.put(message)

    async def _main(self) -> None:
        await self._init()
        server = await self._serve()

        tasks = [
            asyncio.create_task(self._handle_directs()),
            asyncio.create_task(self._handle_broadcasts()),
        ]

        await server.wait_closed()

        for task in tasks:
            task.cancel()

        await self._cleanup()

    def run(self) -> None:
        asyncio.run(self._main())
