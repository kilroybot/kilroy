from typing import Annotated, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from kilroy.config import Config


class BaseMessage(BaseModel):
    id: UUID


# Incoming


class GetStateMessage(BaseMessage):
    type: Literal["get_state"] = "get_state"


class CreateMessage(BaseMessage):
    type: Literal["create"] = "create"
    config: Config


class DestroyMessage(BaseMessage):
    type: Literal["destroy"] = "destroy"


class StartMessage(BaseMessage):
    type: Literal["start"] = "start"


class StartOfflineMessage(BaseMessage):
    type: Literal["start_offline"] = "start_offline"


class StopOfflineMessage(BaseMessage):
    type: Literal["stop_offline"] = "stop_offline"


class StartOnlineMessage(BaseMessage):
    type: Literal["start_online"] = "start_online"


class StopOnlineMessage(BaseMessage):
    type: Literal["stop_online"] = "stop_online"


class StopMessage(BaseMessage):
    type: Literal["stop"] = "stop"


class IncomingMessage(BaseModel):
    __root__: Annotated[
        Union[
            CreateMessage,
            DestroyMessage,
            StartMessage,
            StartOfflineMessage,
            StopOfflineMessage,
            StartOnlineMessage,
            StopOnlineMessage,
            StopMessage,
        ],
        Field(discriminator="type"),
    ]


# Outgoing


class BaseOutgoingMessage(BaseMessage):
    id: UUID = Field(default_factory=uuid4)


class StateMessage(BaseOutgoingMessage):
    type: Literal["state"] = "state"
    created: bool
    running: bool
    offline_training: bool
    online_training: bool
    config: Optional[Config] = None


StateChange = Literal[
    "created",
    "started",
    "started_offline",
    "stopped_offline",
    "started_online",
    "stopped_online",
    "stopped",
    "destroyed",
]


class StateChangeMessage(BaseOutgoingMessage):
    type: Literal["state_change"] = "state_change"
    change: StateChange


class InfoMessage(BaseOutgoingMessage):
    type: Literal["info"] = "info"
    message: str


class ErrorMessage(BaseOutgoingMessage):
    type: Literal["error"] = "error"
    response_to: Optional[UUID] = None
    message: str


class OutgoingMessage(BaseModel):
    __root__: Annotated[
        Union[
            StateMessage,
            StateChangeMessage,
            InfoMessage,
            ErrorMessage,
        ],
        Field(discriminator="type"),
    ]
