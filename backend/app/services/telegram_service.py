import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings


class TelegramService:
    @staticmethod
    def send_message(settings: Settings, text: str, chat_id: str | None = None) -> str:
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not configured.")
        destination = chat_id or settings.telegram_chat_id
        if not destination:
            raise ValueError("TELEGRAM_CHAT_ID is not configured and no chat_id was provided.")

        request = Request(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            data=json.dumps({"chat_id": destination, "text": text}).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(
                f"Telegram sendMessage failed with HTTP status {exc.code}."
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Telegram sendMessage could not be completed.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Telegram sendMessage returned invalid JSON.") from exc

        message_id = result.get("result", {}).get("message_id") if result.get("ok") else None
        if message_id is None:
            raise RuntimeError("Telegram did not confirm that the message was sent.")
        return str(message_id)
