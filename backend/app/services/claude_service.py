import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings


class ClaudeNarrativeClient:
    ALLOWED_FIELDS = {
        "delivery_state",
        "session_narrative",
    }
    TRADE_INSTRUCTION_PATTERN = re.compile(
        r"\b(buy|sell|long|short|entry|enter|stop[\s-]?loss|take[\s-]?profit|"
        r"position\s+size|lot\s+size)\b",
        re.IGNORECASE,
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, context: dict[str, object]) -> dict[str, str]:
        if not self.settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not configured. Add it locally or use provider 'rules'."
            )

        api_format = self.settings.anthropic_api_format.strip().lower()
        if api_format == "openai":
            text = self._generate_openai_compatible(context)
        elif api_format == "anthropic":
            text = self._generate_anthropic_messages(context)
        else:
            raise ValueError("ANTHROPIC_API_FORMAT must be 'anthropic' or 'openai'.")

        try:
            content = json.loads(self._strip_json_fence(text))
        except json.JSONDecodeError as exc:
            raise RuntimeError("Claude narrative content was not valid JSON.") from exc

        narrative = {
            key: value.strip()
            for key, value in content.items()
            if key in self.ALLOWED_FIELDS and isinstance(value, str) and value.strip()
        }
        if set(narrative) != self.ALLOWED_FIELDS:
            raise RuntimeError("Claude narrative content did not contain all required fields.")
        if any(self.TRADE_INSTRUCTION_PATTERN.search(value) for value in narrative.values()):
            raise RuntimeError("Claude narrative content contained a disallowed execution instruction.")
        return narrative

    def _generate_anthropic_messages(self, context: dict[str, object]) -> str:
        payload = {
            "model": self.settings.anthropic_model,
            "max_tokens": 700,
            "system": self._system_prompt(),
            "messages": [
                {
                    "role": "user",
                    "content": "Structured backend context:\n"
                    + json.dumps(context, default=str, ensure_ascii=True),
                }
            ],
        }
        request = Request(
            f"{self.settings.anthropic_base_url.rstrip('/')}/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers("anthropic"),
            method="POST",
        )

        try:
            with urlopen(request, timeout=30) as response:
                message = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(
                f"Claude narrative request failed with HTTP status {exc.code}."
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Claude narrative request could not be completed.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Claude narrative response was not valid JSON.") from exc

        return "".join(
            block.get("text", "")
            for block in message.get("content", [])
            if block.get("type") == "text"
        ).strip()

    def _generate_openai_compatible(self, context: dict[str, object]) -> str:
        payload = {
            "model": self.settings.anthropic_model,
            "max_tokens": 700,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": "Structured backend context:\n"
                    + json.dumps(context, default=str, ensure_ascii=True),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        request = Request(
            f"{self.settings.anthropic_base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers("openai"),
            method="POST",
        )

        try:
            with urlopen(request, timeout=30) as response:
                message = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(
                f"Claude narrative request failed with HTTP status {exc.code}."
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Claude narrative request could not be completed.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Claude narrative response was not valid JSON.") from exc

        choices = message.get("choices", [])
        if not choices:
            raise RuntimeError("Claude narrative response did not include choices.")
        content = choices[0].get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Claude narrative response content was empty.")
        return content.strip()

    def _headers(self, api_format: str) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        scheme = self.settings.anthropic_auth_scheme.strip().lower()
        if scheme == "auto":
            scheme = "bearer" if api_format == "openai" else "x-api-key"
        if scheme == "bearer":
            headers["authorization"] = f"Bearer {self.settings.anthropic_api_key}"
        elif scheme == "x-api-key":
            headers["x-api-key"] = self.settings.anthropic_api_key
        elif scheme == "both":
            headers["authorization"] = f"Bearer {self.settings.anthropic_api_key}"
            headers["x-api-key"] = self.settings.anthropic_api_key
        else:
            raise ValueError("ANTHROPIC_AUTH_SCHEME must be 'auto', 'bearer', 'x-api-key', or 'both'.")
        if api_format == "anthropic":
            headers["anthropic-version"] = self.settings.anthropic_api_version
        return headers

    @staticmethod
    def _system_prompt() -> str:
        path = Path(__file__).resolve().parents[1] / "prompts" / "shadow_delivery_reasoning.txt"
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _strip_json_fence(value: str) -> str:
        if value.startswith("```") and value.endswith("```"):
            lines = value.splitlines()
            return "\n".join(lines[1:-1]).strip()
        return value
