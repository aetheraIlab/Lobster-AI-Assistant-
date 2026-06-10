from __future__ import annotations

import json
import mimetypes
import shlex
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as email_policy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from lobster_assistant.assistant import Assistant
from lobster_assistant.config import AssistantConfig


STATIC_DIR = Path(__file__).parent / "static"


@dataclass(slots=True)
class AssistantHttpServer:
    assistant: Assistant
    config: AssistantConfig
    host: str | None = None
    port: int | None = None

    def create_server(self) -> ThreadingHTTPServer:
        handler = self._make_handler()
        address = (self.host or self.config.http_host, self.port or self.config.http_port)
        return ThreadingHTTPServer(address, handler)

    def serve_forever(self) -> None:
        server = self.create_server()
        address = server.server_address
        print(f"Local assistant HTTP server listening on http://{address[0]}:{address[1]}")
        server.serve_forever()

    def _make_handler(self):
        assistant = self.assistant
        config = self.config

        class Handler(BaseHTTPRequestHandler):
            server_version = "LobsterAssistant/0.1"

            def do_GET(self) -> None:
                if self.path.startswith("/webhooks/whatsapp"):
                    self._handle_whatsapp_verify(config)
                    return
                if self.path in {"/", "/index.html"}:
                    self._send_file(STATIC_DIR / "index.html")
                    return
                if self.path.startswith("/static/"):
                    relative = self.path.removeprefix("/static/").split("?", 1)[0]
                    self._send_file(STATIC_DIR / relative)
                    return
                if self.path == "/health":
                    self._send_json({"ok": True, "name": config.name})
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:
                if self.path == "/api/chat":
                    self._handle_chat(assistant)
                    return
                if self.path == "/api/voice":
                    self._handle_voice(assistant, config)
                    return
                if self.path.startswith("/webhooks/whatsapp"):
                    self._handle_whatsapp_message(assistant, config)
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def log_message(self, format: str, *args: object) -> None:
                print(f"http: {format % args}")

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))

            def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def _send_text(self, text: str, status: int = 200) -> None:
                body = text.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_file(self, path: Path) -> None:
                try:
                    resolved = path.resolve()
                    static_root = STATIC_DIR.resolve()
                    if not resolved.is_relative_to(static_root) or not resolved.exists():
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    body = resolved.read_bytes()
                except OSError:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _handle_chat(self, assistant: Assistant) -> None:
                try:
                    payload = self._read_json()
                    text = str(payload.get("text", ""))
                    user = str(payload.get("user", "voice-web"))
                    reply = assistant.handle_message("web", user, text, {"source": "web"})
                    self._send_json({"reply": reply})
                except Exception as exc:
                    self._send_json({"error": str(exc)}, status=500)

            def _handle_voice(
                self, assistant: Assistant, config: AssistantConfig
            ) -> None:
                try:
                    text = self._transcribe_upload(config)
                    reply = assistant.handle_message(
                        "voice", "phone", text, {"source": "voice-web"}
                    )
                    self._send_json({"text": text, "reply": reply})
                except Exception as exc:
                    self._send_json({"error": str(exc)}, status=500)

            def _transcribe_upload(self, config: AssistantConfig) -> str:
                command = config.voice.stt_command.strip()
                if not command:
                    raise RuntimeError(
                        "No local STT command is configured. Use browser speech mode or run setup."
                    )
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                audio = _extract_multipart_file(
                    self.headers.get("Content-Type", ""), body, "audio"
                )
                with tempfile.TemporaryDirectory() as temp_dir:
                    audio_path = Path(temp_dir) / "input.webm"
                    text_path = Path(temp_dir) / "output.txt"
                    audio_path.write_bytes(audio)
                    parts = [
                        part.format(input=str(audio_path), output=str(text_path))
                        for part in shlex.split(command)
                    ]
                    subprocess.run(parts, check=True, timeout=120)
                    return text_path.read_text(encoding="utf-8").strip()

            def _handle_whatsapp_verify(self, config: AssistantConfig) -> None:
                from urllib.parse import parse_qs, urlparse

                connector = config.connectors.get("whatsapp")
                settings = connector.settings if connector else {}
                verify_token = str(settings.get("verify_token", ""))
                query = parse_qs(urlparse(self.path).query)
                mode = query.get("hub.mode", [""])[0]
                token = query.get("hub.verify_token", [""])[0]
                challenge = query.get("hub.challenge", [""])[0]
                if mode == "subscribe" and token == verify_token:
                    self._send_text(challenge)
                    return
                self.send_error(HTTPStatus.FORBIDDEN)

            def _handle_whatsapp_message(
                self, assistant: Assistant, config: AssistantConfig
            ) -> None:
                try:
                    payload = self._read_json()
                    messages = _extract_whatsapp_text_messages(payload)
                    for message in messages:
                        reply = assistant.handle_message(
                            "whatsapp",
                            message["from"],
                            message["text"],
                            {"source": "whatsapp"},
                        )
                        _send_whatsapp_reply(config, message["from"], reply)
                    self._send_json({"ok": True, "handled": len(messages)})
                except Exception as exc:
                    self._send_json({"error": str(exc)}, status=500)

        return Handler


def _extract_multipart_file(content_type: str, body: bytes, field_name: str) -> bytes:
    if not content_type.lower().startswith("multipart/form-data"):
        raise RuntimeError("Expected multipart/form-data upload.")
    synthetic_headers = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8")
    message = BytesParser(policy=email_policy).parsebytes(synthetic_headers + body)
    if not message.is_multipart():
        raise RuntimeError("Malformed multipart upload.")
    for part in message.iter_parts():
        params = dict(part.get_params(header="content-disposition") or [])
        if params.get("name") == field_name:
            payload = part.get_payload(decode=True)
            if payload:
                return bytes(payload)
    raise RuntimeError(f"Missing {field_name!r} upload.")


def _extract_whatsapp_text_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                text = (message.get("text") or {}).get("body")
                sender = message.get("from")
                if text and sender:
                    found.append({"from": str(sender), "text": str(text)})
    return found


def _send_whatsapp_reply(config: AssistantConfig, recipient: str, text: str) -> None:
    connector = config.connectors.get("whatsapp")
    if not connector or not connector.enabled:
        return
    settings = connector.settings
    token = str(settings.get("access_token", "")).strip()
    phone_number_id = str(settings.get("phone_number_id", "")).strip()
    api_version = str(settings.get("api_version", "v21.0")).strip()
    if not token or not phone_number_id:
        raise RuntimeError("WhatsApp access_token and phone_number_id are required.")
    endpoint = (
        f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    )
    payload = json.dumps(
        {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": text},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"WhatsApp reply failed: {exc}") from exc
