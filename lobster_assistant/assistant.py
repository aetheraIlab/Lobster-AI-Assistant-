from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import AssistantConfig
from .llm import LLM, build_llm
from .memory import MemoryStore, to_llm_messages


@dataclass(slots=True)
class Assistant:
    config: AssistantConfig
    memory: MemoryStore
    llm: LLM

    @classmethod
    def create(cls, config: AssistantConfig) -> "Assistant":
        memory = MemoryStore(config.resolved_database_path())
        llm = build_llm(config)
        return cls(config=config, memory=memory, llm=llm)

    def handle_message(
        self,
        channel: str,
        user_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        clean_text = text.strip()
        if not clean_text:
            return "Send me a little text and I will scuttle into action."

        self.memory.add_message(channel, user_id, "user", clean_text)
        history = self.memory.recent_messages(channel, user_id, limit=14)
        messages = [
            {"role": "system", "content": self._system_prompt(channel, metadata or {})},
            *to_llm_messages(history),
        ]
        reply = self.llm.generate(messages).strip()
        self.memory.add_message(channel, user_id, "assistant", reply)
        return reply

    def _system_prompt(self, channel: str, metadata: dict[str, Any]) -> str:
        context = [
            self.config.personality,
            f"Your display name is {self.config.name}.",
            f"You are speaking with {self.config.owner_name} through {channel}.",
            "Prefer practical answers. Ask one clear question only when necessary.",
            "Do not reveal secrets, tokens, or private config values.",
        ]
        source = metadata.get("source")
        if source:
            context.append(f"Message source: {source}.")
        return "\n".join(context)
