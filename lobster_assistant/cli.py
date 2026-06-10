from __future__ import annotations

import argparse
import getpass
import importlib.util
import socket
import sys
import threading
import urllib.error
import urllib.request

from .assistant import Assistant
from .config import AssistantConfig, ConnectorConfig, default_config_path, load_config, save_config
from .connectors.manager import ConnectorManager
from .voice.server import AssistantHttpServer


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lobster", description="Local personal AI assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup", help="Run the guided setup wizard")
    subparsers.add_parser("chat", help="Chat with the assistant in this terminal")
    subparsers.add_parser("doctor", help="Check local configuration and dependencies")
    subparsers.add_parser("config-path", help="Print the active config path")

    run_parser = subparsers.add_parser("run", help="Run the always-on assistant")
    run_parser.add_argument("--host", help="HTTP host override")
    run_parser.add_argument("--port", type=int, help="HTTP port override")

    args = parser.parse_args(argv)
    if args.command == "setup":
        run_setup()
    elif args.command == "chat":
        run_chat()
    elif args.command == "run":
        run_server(host=args.host, port=args.port)
    elif args.command == "doctor":
        run_doctor()
    elif args.command == "config-path":
        print(default_config_path())


def run_setup() -> None:
    print("Lobster Assistant setup")
    print("Press Enter to accept defaults. Tokens are stored locally in your config file.")
    existing = load_config()
    config = AssistantConfig()
    config.name = prompt("Assistant name", existing.name or config.name)
    config.owner_name = prompt("Your name", existing.owner_name or config.owner_name)
    config.model_provider = prompt_choice("Model provider", ["ollama", "fallback"], existing.model_provider)
    config.model = prompt("Ollama model", existing.model or config.model)
    config.ollama_url = prompt("Ollama URL", existing.ollama_url or config.ollama_url)
    config.http_host = prompt("HTTP host", existing.http_host or config.http_host)
    config.http_port = int(prompt("HTTP port", str(existing.http_port or config.http_port)))

    config.voice.stt_command = prompt(
        "Local STT command, optional. Use {input} and {output}",
        existing.voice.stt_command,
    )

    configure_telegram(config, existing)
    configure_discord(config, existing)
    configure_slack(config, existing)
    configure_whatsapp(config, existing)

    path = save_config(config)
    print(f"Saved config to {path}")
    print("Run with: python -m lobster_assistant run")


def configure_telegram(config: AssistantConfig, existing: AssistantConfig) -> None:
    prior = existing.connectors.get("telegram", ConnectorConfig())
    enabled = prompt_yes_no("Enable Telegram bot", prior.enabled)
    settings = dict(prior.settings)
    if enabled:
        settings["bot_token"] = prompt_secret("Telegram bot token", settings.get("bot_token", ""))
        settings["api_base"] = prompt("Telegram API base, optional", settings.get("api_base", ""))
    config.connectors["telegram"] = ConnectorConfig(enabled=enabled, settings=settings)


def configure_discord(config: AssistantConfig, existing: AssistantConfig) -> None:
    prior = existing.connectors.get("discord", ConnectorConfig())
    enabled = prompt_yes_no("Enable Discord bot", prior.enabled)
    settings = dict(prior.settings)
    if enabled:
        settings["bot_token"] = prompt_secret("Discord bot token", settings.get("bot_token", ""))
    config.connectors["discord"] = ConnectorConfig(enabled=enabled, settings=settings)


def configure_slack(config: AssistantConfig, existing: AssistantConfig) -> None:
    prior = existing.connectors.get("slack", ConnectorConfig())
    enabled = prompt_yes_no("Enable Slack Socket Mode", prior.enabled)
    settings = dict(prior.settings)
    if enabled:
        settings["bot_token"] = prompt_secret("Slack bot token (xoxb-...)", settings.get("bot_token", ""))
        settings["app_token"] = prompt_secret("Slack app token (xapp-...)", settings.get("app_token", ""))
    config.connectors["slack"] = ConnectorConfig(enabled=enabled, settings=settings)


def configure_whatsapp(config: AssistantConfig, existing: AssistantConfig) -> None:
    prior = existing.connectors.get("whatsapp", ConnectorConfig())
    enabled = prompt_yes_no("Enable WhatsApp Business webhook", prior.enabled)
    settings = dict(prior.settings)
    if enabled:
        settings["verify_token"] = prompt_secret("WhatsApp webhook verify token", settings.get("verify_token", ""))
        settings["access_token"] = prompt_secret("WhatsApp access token", settings.get("access_token", ""))
        settings["phone_number_id"] = prompt("WhatsApp phone number ID", settings.get("phone_number_id", ""))
        settings["api_version"] = prompt("Meta Graph API version", settings.get("api_version", "v21.0"))
    config.connectors["whatsapp"] = ConnectorConfig(enabled=enabled, settings=settings)


def run_chat() -> None:
    assistant = Assistant.create(load_config())
    print(f"{assistant.config.name} is ready. Ctrl+C or blank line to exit.")
    try:
        while True:
            text = input("> ").strip()
            if not text:
                break
            print(assistant.handle_message("terminal", "local-user", text))
    except KeyboardInterrupt:
        print()


def run_server(host: str | None = None, port: int | None = None) -> None:
    config = load_config()
    assistant = Assistant.create(config)
    http = AssistantHttpServer(assistant, config, host=host, port=port)
    server = http.create_server()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True, name="http")
    server_thread.start()
    bound_host, bound_port = server.server_address
    print(f"Local assistant HTTP server listening on http://{bound_host}:{bound_port}")
    local_ip = discover_lan_ip()
    active_host = host or config.http_host
    print(f"Phone URL on this network: http://{local_ip}:{bound_port}")
    if active_host == "127.0.0.1":
        print("Tip: use --host 0.0.0.0 if you want your phone to reach this server.")
    manager = ConnectorManager(assistant, config)
    manager.start_enabled()
    manager.keep_alive()


def run_doctor() -> None:
    config = load_config()
    print(f"Config: {default_config_path()}")
    print(f"Memory: {config.resolved_database_path()}")
    print(f"HTTP: http://{config.http_host}:{config.http_port}")
    if config.model_provider == "ollama":
        ok = check_url(config.ollama_url.rstrip("/") + "/api/tags")
        print(f"Ollama: {'ok' if ok else 'not reachable'} ({config.ollama_url})")
    for name, connector in config.connectors.items():
        state = "enabled" if connector.enabled else "disabled"
        print(f"{name}: {state}")
    print(f"discord.py installed: {module_exists('discord')}")
    print(f"slack_bolt installed: {module_exists('slack_bolt')}")


def prompt(label: str, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def prompt_choice(label: str, choices: list[str], default: str) -> str:
    while True:
        value = prompt(f"{label} ({'/'.join(choices)})", default)
        if value in choices:
            return value
        print(f"Choose one of: {', '.join(choices)}")


def prompt_yes_no(label: str, default: bool) -> bool:
    default_text = "Y/n" if default else "y/N"
    while True:
        value = input(f"{label} [{default_text}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please answer y or n.")


def prompt_secret(label: str, default: str) -> str:
    suffix = " [saved]" if default else ""
    value = getpass.getpass(f"{label}{suffix}: ").strip()
    return value or default


def check_url(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            response.read(1)
        return True
    except urllib.error.URLError:
        return False


def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def discover_lan_ip() -> str:
    try:
        host = socket.gethostname()
        candidates = socket.gethostbyname_ex(host)[2]
        for candidate in candidates:
            if not candidate.startswith("127."):
                return candidate
    except OSError:
        pass
    return "127.0.0.1"


if __name__ == "__main__":
    main(sys.argv[1:])
