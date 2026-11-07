from __future__ import annotations

import json
from typing import cast

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from revenueos.progressive_transcription_contracts import MAX_PROGRESSIVE_AUDIO_BASE64_CHARACTERS

MAX_PROGRESSIVE_AUDIO_REQUEST_BYTES = MAX_PROGRESSIVE_AUDIO_BASE64_CHARACTERS + 2_048


class ProgressiveAudioBodyLimitMiddleware:
    """Bound the progressive audio JSON envelope before request parsing."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._is_progressive_audio_request(scope):
            await self._app(scope, receive, send)
            return
        content_length = self._content_length(scope)
        if content_length is None:
            pass
        elif content_length < 0:
            await self._send_error(scope, send, "invalid_content_length", "The request Content-Length is invalid.", 400)
            return
        elif content_length > MAX_PROGRESSIVE_AUDIO_REQUEST_BYTES:
            await self._send_too_large(scope, send)
            return

        body = bytearray()
        disconnected = False
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                disconnected = True
                break
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > MAX_PROGRESSIVE_AUDIO_REQUEST_BYTES:
                await self._send_too_large(scope, send)
                return
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                if disconnected:
                    return {"type": "http.disconnect"}
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self._app(scope, replay_receive, send)

    @staticmethod
    def _is_progressive_audio_request(scope: Scope) -> bool:
        if scope["type"] != "http" or scope.get("method") != "POST":
            return False
        path = cast(str, scope.get("path", ""))
        return (
            path.startswith("/api/v1/interactions/")
            and "/progressive-transcription/sessions/" in path
            and path.endswith("/audio")
        )

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for raw_name, raw_value in scope.get("headers", []):
            if raw_name.lower() != b"content-length":
                continue
            try:
                return int(raw_value.decode("ascii"))
            except (UnicodeDecodeError, ValueError):
                return -1
        return None

    async def _send_too_large(self, scope: Scope, send: Send) -> None:
        await self._send_error(
            scope,
            send,
            "progressive_audio_request_too_large",
            "The progressive audio request is too large.",
            413,
        )

    @staticmethod
    async def _send_error(
        scope: Scope,
        send: Send,
        code: str,
        message: str,
        status_code: int,
    ) -> None:
        state = scope.get("state")
        request_id = state.get("request_id", "unknown") if isinstance(state, dict) else "unknown"
        body = json.dumps(
            {"code": code, "message": message, "requestId": request_id},
            separators=(",", ":"),
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
