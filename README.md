# Lobster Assistant

A private, local-first personal AI assistant you can run on your own devices. It keeps the assistant brain, memory, setup, and voice web UI local. Chat apps still use their normal networks, so messages sent through WhatsApp, Discord, Telegram, or Slack pass through those services before reaching your local machine.

## What works

- Local assistant core with SQLite memory.
- Ollama integration for fully local LLM responses.
- Fallback local responder when Ollama is not running.
- Guided terminal setup: `python -m lobster_assistant setup`.
- Always-on runner: `python -m lobster_assistant run`.
- Telegram long-polling connector.
- Discord connector through `discord.py` when installed.
- Slack Socket Mode connector through `slack-bolt` when installed.
- WhatsApp Business Cloud API webhook receiver and sender.
- Phone-friendly local voice/chat page at `http://YOUR-LAN-IP:8765`.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[discord,slack,dev]"
python -m lobster_assistant setup
python -m lobster_assistant run
```

For the most private model path, install Ollama, pull a model, and choose Ollama in the setup wizard:

```powershell
ollama pull llama3.2
```

## Connector Notes

Telegram is the simplest: create a bot with BotFather, paste the token into setup, and the assistant will use long polling. Official docs: <https://core.telegram.org/bots/api>

Discord requires a bot token and the Message Content Intent enabled in the Discord Developer Portal. Install with the `discord` extra. Official docs: <https://discord.com/developers/docs>

Slack requires Socket Mode with a bot token (`xoxb-...`) and app-level token (`xapp-...`). Install with the `slack` extra. Official docs: <https://slack.dev/bolt-python/concepts/socket-mode/>

WhatsApp requires a WhatsApp Business Platform phone number ID and access token. Incoming messages arrive through the local webhook endpoint:

```text
http://YOUR-PUBLIC-OR-TUNNEL-URL/webhooks/whatsapp
```

For local testing, expose the local port with a tunnel you control. WhatsApp cannot deliver webhooks directly to a private LAN address.

Official WhatsApp webhook docs: <https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components>

## Voice On Phone

Start the assistant and open this on your phone while it is on the same network:

```text
http://YOUR-COMPUTER-LAN-IP:8765
```

The browser page supports push-to-talk when the browser exposes speech recognition. For stricter local speech-to-text, configure a local STT command during setup. The command receives an input audio path and should write recognized text to an output text file.

## Privacy Model

- Assistant memory is stored in SQLite on your machine.
- The default LLM provider is Ollama on `localhost`.
- No cloud LLM provider is configured by this project.
- Chat app messages are subject to each platform's transport, retention, and bot/API policies.
- Browser speech APIs vary by platform. Use the local STT command option when you need speech recognition to stay entirely on your device.

## Useful Commands

```powershell
python -m lobster_assistant chat
python -m lobster_assistant doctor
python -m lobster_assistant config-path
python -m lobster_assistant run --host 0.0.0.0 --port 8765
```

## Running as an Always-On Helper

Windows PowerShell helper:

```powershell
.\scripts\start-assistant.ps1
```

For production-style use, run it with your preferred process manager, login item, Task Scheduler, systemd user service, or launchd agent.
