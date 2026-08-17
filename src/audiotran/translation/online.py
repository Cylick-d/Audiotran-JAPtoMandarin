from __future__ import annotations

import json
from typing import Any, Callable
from urllib import request as urllib_request

from .base import TranslationError, TranslationRequest, Translator
from .local import _validate_translation_count

OnlineSender = Callable[[urllib_request.Request], Any]


class OnlineTranslator(Translator):
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        timeout: float = 30.0,
        sender: Callable[..., Any] | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout
        self._sender = sender or urllib_request.urlopen

    def translate(self, request: TranslationRequest) -> list[str]:
        payload = json.dumps(
            {
                "texts": list(request.texts),
                "glossary": dict(request.glossary),
            }
        ).encode("utf-8")
        http_request = urllib_request.Request(
            self._endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self._sender(http_request, timeout=self._timeout) as response:
                _validate_response_status(response)
                body = json.loads(response.read().decode("utf-8"))
        except TranslationError:
            raise
        except Exception as exc:
            raise TranslationError("online translation failed") from RuntimeError(
                _redact_api_key(str(exc), self._api_key)
            )

        if not isinstance(body, dict):
            raise TranslationError("online translation failed")

        translations = body.get("translations")
        if not isinstance(translations, list) or not all(
            isinstance(item, str) for item in translations
        ):
            raise TranslationError("online translation failed")

        return _validate_translation_count(translations, len(request.texts))


def _validate_response_status(response: Any) -> None:
    status = getattr(response, "status", None)
    if status is None and hasattr(response, "getcode"):
        status = response.getcode()
    if isinstance(status, int) and not 200 <= status < 300:
        raise TranslationError("online translation failed")


def _redact_api_key(message: str, api_key: str) -> str:
    return message.replace(api_key, "[REDACTED]")
