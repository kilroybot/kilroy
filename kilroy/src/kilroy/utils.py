import asyncio
from typing import TypeVar

T = TypeVar("T")


async def noop() -> None:
    await asyncio.sleep(0)
