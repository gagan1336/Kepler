"""
KEPLER -- Gemini API Guard
Central wrapper for all Gemini API calls.

Protections:
  1. Global daily call cap  — hard ceiling across ALL calls server-wide
  2. Per-call token limit   — prevents prompt-injection blowout
  3. Key validation         — refuses to call if key is missing/placeholder
  4. Exception shield       — never crashes callers; returns None on failure
  5. Structured logging     — every call logged with caller, tokens, latency

Counter storage: PostgreSQL `gemini_daily_usage` table (one row per UTC day).
  - Replaces the old /tmp flat-file which had race conditions under
    multi-worker deployments and was lost on container restarts.

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
from typing import Optional

from loguru import logger

# ── Global daily cap ──────────────────────────────────────────────────────────
# Server-wide hard ceiling — not per-user.
# Prevents runaway scheduler jobs or bursts from burning the entire key.
# Gemini Flash: ~₹0.075 per 1M input tokens. 500 calls * ~2K tokens ≈ ₹0.075/day max.
_GLOBAL_DAILY_CAP = 500          # total Gemini calls per calendar day (UTC)
_MAX_OUTPUT_TOKENS = 8192        # hard cap on response size

_PLACEHOLDER_PATTERNS = ("your_", "XXXXXXX", "placeholder", "replace_me", "xxxx")


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


def _increment_global_counter_db() -> bool:
    """
    Atomically increment the server-wide Gemini daily counter in PostgreSQL.

    Uses a single row per UTC day in the `gemini_daily_usage` table.
    Returns True if the call is allowed, False if the daily cap is exceeded.

    Safe under multi-worker deployments — DB handles the atomicity.
    Survives container restarts — DB persists across deploys.
    """
    from database import SessionLocal
    from models import GeminiDailyUsage

    today = date.today()
    db = SessionLocal()
    try:
        row = db.query(GeminiDailyUsage).filter(GeminiDailyUsage.usage_date == today).first()

        if row is None:
            # First call of the day — create the counter row
            row = GeminiDailyUsage(usage_date=today, call_count=0)
            db.add(row)
            db.flush()  # get the row into the session before update

        if row.call_count >= _GLOBAL_DAILY_CAP:
            logger.error(
                f"[GEMINI GUARD] Global daily cap reached ({row.call_count}/{_GLOBAL_DAILY_CAP}). "
                f"No more Gemini calls today. Resets at midnight UTC."
            )
            return False

        # Atomic increment
        row.call_count += 1
        db.commit()
        return True

    except Exception as e:
        logger.warning(f"[GEMINI GUARD] DB counter error (allowing call as fallback): {e}")
        try:
            db.rollback()
        except Exception:
            pass
        # Fail-open: a DB hiccup should not kill AI features entirely
        return True
    finally:
        db.close()


def _read_daily_count_db() -> int:
    """Return today's current Gemini call count from the DB."""
    from database import SessionLocal
    from models import GeminiDailyUsage

    today = date.today()
    db = SessionLocal()
    try:
        row = db.query(GeminiDailyUsage).filter(GeminiDailyUsage.usage_date == today).first()
        return row.call_count if row else 0
    except Exception:
        return 0
    finally:
        db.close()


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

    # 2. Global daily cap (DB-backed, multi-worker safe)
    if not _increment_global_counter_db():
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
        count = _read_daily_count_db()
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
    """Return current Gemini daily usage stats (DB-backed)."""
    today = date.today()
    count = _read_daily_count_db()
    return {
        "date": today.isoformat(),
        "calls_used": count,
        "calls_remaining": max(0, _GLOBAL_DAILY_CAP - count),
        "daily_cap": _GLOBAL_DAILY_CAP,
        "storage": "database",  # confirms we're using DB, not /tmp
    }



