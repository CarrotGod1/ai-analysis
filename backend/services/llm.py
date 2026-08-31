import json
from typing import AsyncGenerator

import httpx

from config import settings


class OllamaService:
    def __init__(self):
        self.base_url = settings.ollama_base_url

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("models", [])

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = True,
    ) -> str | AsyncGenerator[str, None]:
        model = model or settings.default_model
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": 0.3,
                "num_ctx": 8192,
            },
        }

        if stream:
            return self._stream_response(payload)
        else:
            return await self._sync_response(payload)

    async def _stream_response(self, payload: dict) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120)) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("done"):
                        break
                    msg = chunk.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        yield content

    async def _sync_response(self, payload: dict) -> str:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120)) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

    async def generate(self, prompt: str, model: str | None = None) -> str:
        model = model or settings.default_model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3},
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(120)) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")


ollama = OllamaService()
