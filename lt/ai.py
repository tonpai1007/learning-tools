"""OpenAI-compatible API client with retry logic and response caching.

Swap providers by changing .env / config.yaml.
"""
import hashlib
import json
import logging
import os
import time
from pathlib import Path

from rich.console import Console

from .config import cfg

console = Console()
logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 30.0  # seconds
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Cache configuration
CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_ENABLED = os.getenv("LT_CACHE", "1") == "1"


def _cache_key(prompt: str, system: str, temperature: float | None, model: str) -> str:
    """Generate a deterministic cache key for an API call."""
    content = f"{model}:{temperature}:{system}:{prompt}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _get_cached_response(key: str) -> str | None:
    """Retrieve a cached response if it exists."""
    if not CACHE_ENABLED:
        return None
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            logger.debug(f"Cache hit: {key[:12]}...")
            return data["response"]
        except (json.JSONDecodeError, KeyError):
            cache_file.unlink(missing_ok=True)
    return None


def _save_cached_response(key: str, response: str, prompt: str, system: str) -> None:
    """Save a response to the cache."""
    if not CACHE_ENABLED:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{key}.json"
    data = {
        "response": response,
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
        "system_hash": hashlib.sha256(system.encode("utf-8")).hexdigest()[:16],
        "cached_at": time.time(),
    }
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def clear_cache() -> int:
    """Clear all cached responses. Returns number of files removed."""
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count


def _client():
    from openai import OpenAI

    return OpenAI(
        api_key=cfg.api_key() or "not-needed",
        base_url=cfg.base_url(),
        max_retries=0,  # We handle retries ourselves for better control
    )


def _is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable."""
    error_str = str(error).lower()
    # Rate limiting
    if "rate limit" in error_str or "429" in error_str:
        return True
    # Server errors
    if any(code in error_str for code in ["500", "502", "503", "504"]):
        return True
    # Connection errors
    if "connection" in error_str or "timeout" in error_str:
        return True
    return False


def complete(
    prompt: str,
    system: str = "You are a helpful study assistant.",
    temperature: float | None = None,
    use_cache: bool = True,
) -> str:
    """Complete a prompt with retry logic and caching."""
    ai = cfg.ai()
    model = ai.get("model", "gpt-4o-mini")
    temp = temperature if temperature is not None else ai.get("temperature", 0.7)
    max_tokens = ai.get("max_tokens", 2048)

    # Check cache first
    key = _cache_key(prompt, system, temp, model)
    if use_cache:
        cached = _get_cached_response(key)
        if cached is not None:
            return cached

    # Make API call with retries
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.debug(f"API call attempt {attempt + 1}/{MAX_RETRIES + 1}")
            resp = _client().chat.completions.create(
                model=model,
                temperature=temp,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            result = (resp.choices[0].message.content or "").strip()

            # Cache the response
            if use_cache:
                _save_cached_response(key, result, prompt, system)

            return result

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES and _is_retryable_error(e):
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                logger.warning(
                    f"Retryable error (attempt {attempt + 1}/{MAX_RETRIES + 1}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                break

    raise last_error  # type: ignore[misc]


def chat(messages: list[dict], temperature: float | None = None) -> str:
    """Chat with retry logic (no caching for multi-turn)."""
    ai = cfg.ai()
    model = ai.get("model", "gpt-4o-mini")
    temp = temperature if temperature is not None else ai.get("temperature", 0.7)
    max_tokens = ai.get("max_tokens", 2048)

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.debug(f"Chat API call attempt {attempt + 1}/{MAX_RETRIES + 1}")
            resp = _client().chat.completions.create(
                model=model,
                temperature=temp,
                max_tokens=max_tokens,
                messages=messages,
            )
            return (resp.choices[0].message.content or "").strip()

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES and _is_retryable_error(e):
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                logger.warning(
                    f"Retryable error (attempt {attempt + 1}/{MAX_RETRIES + 1}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                break

    raise last_error  # type: ignore[misc]


def extract_json(text: str):
    """Parse a JSON object or array out of an LLM response (tolerates markdown fences)."""
    import re

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


def estimate_total_cost(texts: list[str]) -> tuple[int, str]:
    """Estimate total token count and cost for a list of texts.

    Returns (token_count, formatted_string).
    """
    total_chars = sum(len(t) for t in texts)
    total_tokens = total_chars // 4
    return total_tokens, f"~{total_tokens:,} tokens"