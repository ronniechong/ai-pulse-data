import requests

from aipulse.config import NTFY_TOPIC, NTFY_URL

_TIMEOUT = 10


def notify(title: str, message: str, priority: str = "default", tags: str | None = None) -> None:
    if not NTFY_TOPIC:
        return
    headers = {"Title": title, "Priority": priority}
    if tags:
        headers["Tags"] = tags
    try:
        requests.post(
            f"{NTFY_URL}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=_TIMEOUT,
        )
    except requests.RequestException:
        pass
