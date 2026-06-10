from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .base import ConnectorContext, ConnectorError


@dataclass(slots=True)
class TelegramConnector:
    context: ConnectorContext
    name: str = "telegram"

    @property
    def token(self) -> str:
        token = str(self.context.config.settings.get("bot_token", "")).strip()
        if not token:
            raise ConnectorError("Telegram bot_token is missing.")
        return token

    @property
    def api_base(self) -> str:
        configured = str(self.context.config.settings.get("api_base", "")).strip()
        if configured:
            return configured.rstrip("/")
        return f"https://api.telegram.org/bot{self.token}"

    def run_forever(self) -> None:
        offset = int(self.context.config.settings.get("offset", 0) or 0)
        print("Telegram connector is listening.")
        while True:
            try:
                updates = self._get_updates(offset)
                for update in updates:
                    offset = max(offset, int(update["update_id"]) + 1)
                    self._handle_update(update)
            except Exception as exc:
                print(f"Telegram connector error: {exc}")
                time.sleep(5)

    def _get_updates(self, offset: int) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {"offset": offset, "timeout": 30, "allowed_updates": json.dumps(["message"])}
        )
        data = self._request_json(f"{self.api_base}/getUpdates?{params}")
        return list(data.get("result", []))

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        text = message.get("text")
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if not text or chat_id is None:
            return
        user = message.get("from") or {}
        user_id = str(user.get("id") or chat_id)
        reply = self.context.assistant.handle_message(
            "telegram",
            user_id,
            str(text),
            {"source": "telegram", "chat_id": chat_id},
        )
        self.send_message(str(chat_id), reply)

    def send_message(self, chat_id: str, text: str) -> None:
        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode(
            "utf-8"
        )
        self._request_json(f"{self.api_base}/sendMessage", data=payload)

    def _request_json(self, url: str, data: bytes | None = None) -> dict[str, Any]:
        request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise ConnectorError(f"Telegram API request failed: {exc}") from exc
        parsed = json.loads(payload)
        if not parsed.get("ok", False):
            raise ConnectorError(f"Telegram API returned an error: {parsed}")
        return parsed
