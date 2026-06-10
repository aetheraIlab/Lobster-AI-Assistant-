from pathlib import Path

from lobster_assistant.assistant import Assistant
from lobster_assistant.config import AssistantConfig
from lobster_assistant.llm import LobsterFallbackLLM
from lobster_assistant.memory import MemoryStore


def test_assistant_records_and_replies(tmp_path: Path) -> None:
    config = AssistantConfig(name="Captain Test", model_provider="fallback")
    config.database_path = str(tmp_path / "memory.sqlite3")
    assistant = Assistant(
        config=config,
        memory=MemoryStore(config.resolved_database_path()),
        llm=LobsterFallbackLLM("Captain Test"),
    )

    reply = assistant.handle_message("terminal", "me", "hello")

    assert "Captain Test" in reply
    records = assistant.memory.recent_messages("terminal", "me")
    assert [record.role for record in records] == ["user", "assistant"]
