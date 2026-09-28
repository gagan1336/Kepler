"""
KEPLER -- Gemini API Guard
Central wrapper for all Gemini API calls.

Protections:
  1. Global daily call cap  — hard ceiling across ALL calls server-wide
  2. Per-call token limit   — prevents prompt-injection blowout
  3. Key validation         — refuses to call if key is missing/placeholder
  4. Exception shield       — never crashes callers; returns None on failure
  5. Structured logging     — every call logged with caller, tokens, latency

Usage:
    from gemini_guard import gemini_call

    result = gemini_call(
        prompt="Analyse RELIANCE...",
        caller="deep_dive_generator",
        max_tokens=4096,
        temperature=0.3,
    )
    if result is None:
        # quota exhausted or key invalid — use fallback
"""
import time
from datetime import date
from pathlib import Path
from typing import Optional

from loguru import logger

# ── Global daily cap ──────────────────────────────────────────────────────────
# This is a server-wide hard ceiling — not per-user.
# Prevents runaway scheduler jobs or burst from burning the entire key.
# Gemini Flash: ~₹0.075 per 1M input tokens. 500 calls * ~2K tokens = ~₹0.075/day max.
_GLOBAL_DAILY_CAP = 500          # total Gemini calls per calendar day (UTC)
_MAX_OUTPUT_TOKENS = 8192        # hard cap on response size
_COUNTER_FILE = Path("/tmp/kepler_gemini_counter.txt")  # persists across requests

_PLACEHOLDER_PATTERNS = ("your_", "XXXXXXX", "placeholder", "replace_me", "xxxx")


def _read_counter() -> tuple[int, str]:
    """Read (count, date_str) from the counter file."""
    try:
        if _COUNTER_FILE.exists():
            parts = _COUNTER_FILE.read_text().strip().split(",")
            if len(parts) == 2:
                return int(parts[0]), parts[1]
    except Exception:
        pass
    return 0, ""


def _write_counter(count: int, date_str: str):
    try:
        _COUNTER_FILE.write_text(f"{count},{date_str}")
    except Exception:
        pass


def _increment_global_counter() -> bool:
    """
    Increment the global daily counter.
    Returns True if call is allowed, False if cap is exceeded.
    """
    today = date.today().isoformat()
    count, stored_date = _read_counter()

    if stored_date != today:
        # New day — reset counter
        count = 0

    if count >= _GLOBAL_DAILY_CAP:
        logger.error(
            f"[GEMINI GUARD] Global daily cap reached ({count}/{_GLOBAL_DAILY_CAP}). "
            f"No more Gemini calls today. Resets at midnight UTC."
        )
        return False

    _write_counter(count + 1, today)
    return True


def _validate_key(api_key: str) -> bool:
    """Reject placeholder/empty keys."""
    if not api_key or not api_key.strip():
        logger.error("[GEMINI GUARD] GEMINI_API_KEY is not set.")
        return False
    for pattern in _PLACEHOLDER_PATTERNS:
        if pattern.lower() in api_key.lower():
            logger.error(f"[GEMINI GUARD] GEMINI_API_KEY looks like a placeholder: {api_key[:12]}...")
            return False
    if len(api_key) < 20:
        logger.error("[GEMINI GUARD] GEMINI_API_KEY is too short to be valid.")
        return False
    return True


def gemini_call(
    prompt: str,
    caller: str = "unknown",
    model_name: str = "gemini-2.0-flash",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> Optional[str]:
    """
    Make a single Gemini API call with all safety guards applied.

    Args:
        prompt:     The full prompt string.
        caller:     Name of calling module (for logging).
        model_name: Gemini model to use.
        max_tokens: Maximum output tokens (hard-capped at _MAX_OUTPUT_TOKENS).
        temperature: Generation temperature (0.0 - 1.0).

    Returns:
        The response text, or None if:
          - global daily cap exceeded
          - API key missing/invalid
          - Gemini API call failed
    """
    from config import settings

    # 1. Key guard
    if not _validate_key(settings.gemini_api_key):
        return None

    # 2. Global daily cap
    if not _increment_global_counter():
        return None

    # 3. Clamp max_tokens to hard ceiling
    safe_max_tokens = min(max_tokens, _MAX_OUTPUT_TOKENS)

    # 4. Call Gemini
    t0 = time.monotonic()
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=safe_max_tokens,
            ),
        )
        elapsed = round(time.monotonic() - t0, 2)
        count, _ = _read_counter()
        logger.info(
            f"[GEMINI GUARD] caller={caller} model={model_name} "
            f"tokens_out={len(response.text.split())} latency={elapsed}s "
            f"daily_count={count}/{_GLOBAL_DAILY_CAP}"
        )
        return response.text

    except Exception as e:
        elapsed = round(time.monotonic() - t0, 2)
        logger.error(
            f"[GEMINI GUARD] FAILED caller={caller} model={model_name} "
            f"latency={elapsed}s error={e}"
        )
        return None


def get_daily_usage() -> dict:
    """Return current Gemini daily usage stats."""
    today = date.today().isoformat()
    count, stored_date = _read_counter()
    if stored_date != today:
        count = 0
    return {
        "date": today,
        "calls_used": count,
        "calls_remaining": max(0, _GLOBAL_DAILY_CAP - count),
        "daily_cap": _GLOBAL_DAILY_CAP,
    }
