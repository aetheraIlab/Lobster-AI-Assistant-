from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from .config import AssistantConfig


class LLM(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> str:
        ...


@dataclass(slots=True)
class OllamaLLM:
    url: str
    model: str
    timeout_seconds: int = 120

    def generate(self, messages: list[dict[str, str]]) -> str:
        endpoint = self.url.rstrip("/") + "/api/chat"
        payload = json.dumps(
            {"model": self.model, "messages": messages, "stream": False}
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        message = data.get("message", {})
        content = message.get("content", "")
        if not content:
            raise RuntimeError("Ollama returned an empty response.")
        return str(content).strip()


@dataclass(slots=True)
class LobsterFallbackLLM:
    assistant_name: str

    def generate(self, messages: list[dict[str, str]]) -> str:
        latest = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                latest = message.get("content", "")
                break
        if not latest:
            return f"{self.assistant_name} is awake, claws poised, and ready."
        return (
            f"{self.assistant_name} here. I am running in local fallback mode, so I "
            f"cannot reason as deeply as your configured model yet. I heard: {latest!r}. "
            "Start Ollama or choose a local model in setup and I will bring the full "
            "lobster brain online."
        )


@dataclass(slots=True)
class ResilientLLM:
    primary: LLM
    fallback: LLM

    def generate(self, messages: list[dict[str, str]]) -> str:
        try:
            return self.primary.generate(messages)
        except Exception as exc:
            fallback_reply = self.fallback.generate(messages)
            return f"{fallback_reply}\n\nLocal model note: {exc}"


def build_llm(config: AssistantConfig) -> LLM:
    fallback = LobsterFallbackLLM(config.name)
    if config.model_provider.lower() == "ollama":
        ollama = OllamaLLM(config.ollama_url, config.model)
        return ResilientLLM(primary=ollama, fallback=fallback)
    return fallback
