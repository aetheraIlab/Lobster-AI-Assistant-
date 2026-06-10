from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lobster_assistant.assistant import Assistant
from lobster_assistant.config import ConnectorConfig


class Connector(Protocol):
    name: str

    def run_forever(self) -> None:
        ...


@dataclass(slots=True)
class ConnectorContext:
    assistant: Assistant
    config: ConnectorConfig


class ConnectorError(RuntimeError):
    pass
