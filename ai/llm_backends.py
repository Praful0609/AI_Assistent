"""
LLM backend abstraction.
Gemini is the default; protocol allows future OpenAI/Ollama backends.
"""
from typing import Protocol, runtime_checkable
from google import genai
from google.genai import types
from app.config import settings


@runtime_checkable
class LLMBackend(Protocol):
    async def chat_async(self, messages: list[dict], system: str = "") -> str: ...
    def chat(self, messages: list[dict], system: str = "") -> str: ...


class GeminiBackend:
    """
    Gemini LLM backend using the google-genai SDK.
    Uses gemini-2.0-flash by default (fast, cost-effective).
    Swap GEMINI_MODEL in .env for gemini-2.5-pro for deeper analysis.
    """

    def __init__(self, model: str | None = None):
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = model or settings.gemini_model

    def chat(self, messages: list[dict], system: str = "") -> str:
        """Synchronous chat completion."""
        contents = [
            types.Content(
                role=m["role"],
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=0.2,
            max_output_tokens=8192,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )
        return response.text or ""

    async def chat_async(self, messages: list[dict], system: str = "") -> str:
        """Async chat completion for FastAPI endpoints."""
        # google-genai does not yet have a native async client;
        # run in threadpool to avoid blocking the event loop.
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.chat, messages, system)
