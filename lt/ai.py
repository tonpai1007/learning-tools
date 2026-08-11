"""OpenAI-compatible API client. Swap providers by changing .env / config.yaml."""
import json
import re

from rich.console import Console

from .config import cfg

console = Console()


def _client():
    from openai import OpenAI

    return OpenAI(api_key=cfg.api_key() or "not-needed", base_url=cfg.base_url())


def complete(prompt: str, system: str = "You are a helpful study assistant.", temperature: float | None = None) -> str:
    ai = cfg.ai()
    resp = _client().chat.completions.create(
        model=ai.get("model", "gpt-4o-mini"),
        temperature=temperature if temperature is not None else ai.get("temperature", 0.7),
        max_tokens=ai.get("max_tokens", 2048),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def chat(messages: list[dict], temperature: float | None = None) -> str:
    ai = cfg.ai()
    resp = _client().chat.completions.create(
        model=ai.get("model", "gpt-4o-mini"),
        temperature=temperature if temperature is not None else ai.get("temperature", 0.7),
        max_tokens=ai.get("max_tokens", 2048),
        messages=messages,
    )
    return (resp.choices[0].message.content or "").strip()


def extract_json(text: str):
    """Parse a JSON object or array out of an LLM response (tolerates markdown fences)."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    if text.startswith("["):
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end == -1:
            raise ValueError("No JSON array found in response.")
        return json.loads(text[start:end + 1])
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in response.")
    return json.loads(text[start:end + 1])


def estimate_cost(text: str) -> str:
    return f"~{len(text) // 4:,} tokens"
