"""The only module that talks to an AI vendor.

The rest of the app depends on the small `AIProvider` interface, so the vendor
can be swapped (or faked in tests) without touching routes or services.
"""

import logging
from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_FALLBACK_MODEL_PREFIXES = ("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5")


class AIServiceError(Exception):
    """The AI call failed or returned something unusable."""


class AIProvider(Protocol):
    def generate(self, *, system: str, user: str, output: type[T]) -> T:
        """Send one prompt and return the response parsed into `output`."""
        ...


class AnthropicProvider:
    def __init__(self, api_key: str, model: str, effort: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._effort = effort

    def _fallback_params(self) -> dict:
        """If the main model declines, the API retries on a fallback model in the same call.
        Only some models support it (Haiku does not), so it is left out for the others."""
        if not self._model.startswith(_FALLBACK_MODEL_PREFIXES):
            return {}
        return {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    def generate(self, *, system: str, user: str, output: type[T]) -> T:
        try:
            response = self._client.beta.messages.parse(
                model=self._model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=output,
                output_config={"effort": self._effort},
                **self._fallback_params(),
            )
        except anthropic.AuthenticationError as e:
            raise AIServiceError("Invalid or missing ANTHROPIC_API_KEY") from e
        except anthropic.RateLimitError as e:
            raise AIServiceError("AI rate limit reached, try again shortly") from e
        except anthropic.APIStatusError as e:
            logger.error("Anthropic API error %s: %s", e.status_code, e.message)
            raise AIServiceError(f"AI service error ({e.status_code})") from e
        except anthropic.APIConnectionError as e:
            raise AIServiceError("Could not reach the AI service") from e

        if response.stop_reason == "refusal":
            raise AIServiceError("The AI declined to review this text")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            logger.error("Unusable AI response, request_id=%s", response._request_id)
            raise AIServiceError("The AI returned an incomplete response")
        return response.parsed_output


_provider: AIProvider | None = None


def get_provider() -> AIProvider:
    """FastAPI dependency. Tests override it with a fake provider."""
    global _provider
    if _provider is None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise AIServiceError("ANTHROPIC_API_KEY is not set (see backend/.env)")
        _provider = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            effort=settings.anthropic_effort,
        )
    return _provider
