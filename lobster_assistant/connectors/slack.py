from __future__ import annotations

from dataclasses import dataclass

from .base import ConnectorContext, ConnectorError


@dataclass(slots=True)
class SlackConnector:
    context: ConnectorContext
    name: str = "slack"

    def run_forever(self) -> None:
        bot_token = str(self.context.config.settings.get("bot_token", "")).strip()
        app_token = str(self.context.config.settings.get("app_token", "")).strip()
        if not bot_token or not app_token:
            raise ConnectorError("Slack bot_token and app_token are required.")
        try:
            from slack_bolt import App
            from slack_bolt.adapter.socket_mode import SocketModeHandler
        except ImportError as exc:
            raise ConnectorError(
                "Install Slack support with: python -m pip install -e .[slack]"
            ) from exc

        app = App(token=bot_token)
        assistant = self.context.assistant

        @app.event("app_mention")
        def handle_app_mention(body, say) -> None:  # type: ignore[no-untyped-def]
            event = body.get("event", {})
            text = str(event.get("text", "")).strip()
            user_id = str(event.get("user", "unknown"))
            reply = assistant.handle_message(
                "slack",
                user_id,
                text,
                {"source": "slack", "channel": event.get("channel")},
            )
            say(reply)

        @app.event("message")
        def handle_dm(event, say) -> None:  # type: ignore[no-untyped-def]
            if event.get("channel_type") != "im":
                return
            if event.get("subtype") or event.get("bot_id"):
                return
            text = str(event.get("text", "")).strip()
            user_id = str(event.get("user", "unknown"))
            reply = assistant.handle_message(
                "slack",
                user_id,
                text,
                {"source": "slack_dm", "channel": event.get("channel")},
            )
            say(reply)

        print("Slack connector is listening through Socket Mode.")
        SocketModeHandler(app, app_token).start()
