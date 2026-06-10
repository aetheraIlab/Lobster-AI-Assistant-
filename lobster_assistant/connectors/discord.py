from __future__ import annotations

from dataclasses import dataclass

from .base import ConnectorContext, ConnectorError


@dataclass(slots=True)
class DiscordConnector:
    context: ConnectorContext
    name: str = "discord"

    def run_forever(self) -> None:
        token = str(self.context.config.settings.get("bot_token", "")).strip()
        if not token:
            raise ConnectorError("Discord bot_token is missing.")
        try:
            import discord
        except ImportError as exc:
            raise ConnectorError(
                "Install Discord support with: python -m pip install -e .[discord]"
            ) from exc

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        assistant = self.context.assistant

        @client.event
        async def on_ready() -> None:
            print(f"Discord connector logged in as {client.user}.")

        @client.event
        async def on_message(message) -> None:  # type: ignore[no-untyped-def]
            if message.author == client.user:
                return
            if message.guild and client.user not in message.mentions:
                return
            content = str(message.content or "").strip()
            mention = getattr(client.user, "mention", "")
            if mention:
                content = content.replace(mention, "").strip()
            if not content:
                return
            reply = assistant.handle_message(
                "discord",
                str(message.author.id),
                content,
                {"source": "discord", "channel_id": str(message.channel.id)},
            )
            await message.channel.send(reply)

        client.run(token)
