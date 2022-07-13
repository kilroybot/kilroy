from abc import ABC, abstractmethod
from typing import Tuple
from uuid import UUID


class Controller(ABC):
    @abstractmethod
    async def init(self) -> None:
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        pass

    @abstractmethod
    async def handle_message(self, sender: UUID, message: str) -> None:
        pass

    @abstractmethod
    async def poll_direct(self) -> Tuple[UUID, str]:
        pass

    @abstractmethod
    async def poll_broadcast(self) -> str:
        pass
