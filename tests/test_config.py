from pathlib import Path

from lobster_assistant.config import AssistantConfig, ConnectorConfig, load_config, save_config


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    config = AssistantConfig(name="Claw Unit")
    config.connectors["telegram"] = ConnectorConfig(
        enabled=True, settings={"bot_token": "123:abc"}
    )

    save_config(config, path)
    loaded = load_config(path)

    assert loaded.name == "Claw Unit"
    assert loaded.connectors["telegram"].enabled is True
    assert loaded.connectors["telegram"].settings["bot_token"] == "123:abc"
