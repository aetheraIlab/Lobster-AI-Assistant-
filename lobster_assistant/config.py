from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


APP_DIR_NAME = ".lobster-assistant"


def default_home() -> Path:
    configured = os.environ.get("LOBSTER_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / APP_DIR_NAME


def default_config_path() -> Path:
    configured = os.environ.get("LOBSTER_CONFIG")
    if configured:
        return Path(configured).expanduser()
    return default_home() / "config.json"


@dataclass(slots=True)
class ConnectorConfig:
    enabled: bool = False
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VoiceConfig:
    enabled: bool = True
    stt_command: str = ""
    tts_in_browser: bool = True


@dataclass(slots=True)
class AssistantConfig:
    name: str = "Captain Clawdia"
    owner_name: str = "friend"
    personality: str = (
        "You are a private local personal AI assistant with a witty lobster theme. "
        "Be concise, helpful, calm, and a little quirky. Never claim to be cloud-hosted."
    )
    model_provider: str = "ollama"
    model: str = "llama3.2"
    ollama_url: str = "http://127.0.0.1:11434"
    database_path: str = ""
    http_host: str = "127.0.0.1"
    http_port: int = 8765
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    connectors: dict[str, ConnectorConfig] = field(
        default_factory=lambda: {
            "telegram": ConnectorConfig(),
            "discord": ConnectorConfig(),
            "slack": ConnectorConfig(),
            "whatsapp": ConnectorConfig(),
        }
    )

    def resolved_database_path(self) -> Path:
        if self.database_path:
            return Path(self.database_path).expanduser()
        return default_home() / "memory.sqlite3"


def _connector_from_dict(value: Any) -> ConnectorConfig:
    if isinstance(value, ConnectorConfig):
        return value
    if not isinstance(value, dict):
        return ConnectorConfig()
    return ConnectorConfig(
        enabled=bool(value.get("enabled", False)),
        settings=dict(value.get("settings", {})),
    )


def config_from_dict(data: dict[str, Any]) -> AssistantConfig:
    voice_data = data.get("voice", {})
    voice = VoiceConfig(**voice_data) if isinstance(voice_data, dict) else VoiceConfig()
    connectors = {
        "telegram": ConnectorConfig(),
        "discord": ConnectorConfig(),
        "slack": ConnectorConfig(),
        "whatsapp": ConnectorConfig(),
    }
    for name, value in dict(data.get("connectors", {})).items():
        connectors[name] = _connector_from_dict(value)

    allowed = {
        "name",
        "owner_name",
        "personality",
        "model_provider",
        "model",
        "ollama_url",
        "database_path",
        "http_host",
        "http_port",
    }
    kwargs = {key: data[key] for key in allowed if key in data}
    return AssistantConfig(**kwargs, voice=voice, connectors=connectors)


def load_config(path: Path | None = None) -> AssistantConfig:
    config_path = path or default_config_path()
    if not config_path.exists():
        return AssistantConfig()
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return config_from_dict(data)


def save_config(config: AssistantConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    temp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temp_path.replace(config_path)
    return config_path
