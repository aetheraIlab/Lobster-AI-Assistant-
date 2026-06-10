from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from lobster_assistant.assistant import Assistant
from lobster_assistant.config import AssistantConfig

from .base import ConnectorContext
from .discord import DiscordConnector
from .slack import SlackConnector
from .telegram import TelegramConnector


CONNECTOR_TYPES = {
    "telegram": TelegramConnector,
    "discord": DiscordConnector,
    "slack": SlackConnector,
}


@dataclass(slots=True)
class ConnectorManager:
    assistant: Assistant
    config: AssistantConfig
    threads: list[threading.Thread] = field(default_factory=list)

    def start_enabled(self) -> None:
        for name, connector_config in self.config.connectors.items():
            if not connector_config.enabled:
                continue
            connector_type = CONNECTOR_TYPES.get(name)
            if connector_type is None:
                if name == "whatsapp":
                    print("WhatsApp is handled by the HTTP webhook server.")
                else:
                    print(f"Unknown connector {name!r}; skipping.")
                continue
            context = ConnectorContext(self.assistant, connector_config)
            connector = connector_type(context)
            thread = threading.Thread(
                target=self._run_connector,
                args=(connector.run_forever, name),
                daemon=True,
                name=f"connector-{name}",
            )
            thread.start()
            self.threads.append(thread)

    def _run_connector(self, run_forever, name: str) -> None:  # type: ignore[no-untyped-def]
        while True:
            try:
                run_forever()
            except Exception as exc:
                print(f"{name} connector stopped: {exc}")
                time.sleep(10)

    def keep_alive(self) -> None:
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("Shutting down connectors.")
