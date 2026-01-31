from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WebhookNotification:
    url: str
    timeout_seconds: float = 10.0


def post_webhook_json(notification: WebhookNotification, payload: dict[str, Any]) -> None:
    try:
        import requests  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "requests is required for webhook notifications. Install it or remove --webhook-url."
        ) from e

    resp = requests.post(notification.url, json=payload, timeout=notification.timeout_seconds)
    resp.raise_for_status()
