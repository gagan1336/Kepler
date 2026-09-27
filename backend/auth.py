"""
KEPLER -- Authentication
Verifies Supabase JWTs (ES256 via JWKS), upserts users into local DB on first contact.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import urllib.request

import jwt as pyjwt
from jwt.algorithms import ECAlgorithm
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from loguru import logger

from config import settings
from database import get_db
from models import User

# ── Password hashing (kept for legacy / admin tooling) ───────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── HTTP Bearer scheme — reads Authorization: Bearer <token> ─────────────────
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWKS public key cache (loaded once at startup) ────────────────────────────
_JWKS_PUBLIC_KEYS: Dict[str, Any] = {}   # kid -> public key object
_SUPABASE_URL = "https://bvtvbstbspduoxuurbin.supabase.co"

def _load_jwks() -> None:
    """Fetch and cache Supabase's JWKS public keys for ES256 verification."""
    global _JWKS_PUBLIC_KEYS
    try:
        url = f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        req = urllib.request.Request(url, headers={
            "apikey": settings.supabase_anon_key or "",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        for key in data.get("keys", []):
            kid = key.get("kid", "default")
            _JWKS_PUBLIC_KEYS[kid] = ECAlgorithm.from_jwk(json.dumps(key))
        logger.info(f"✅ Loaded {len(_JWKS_PUBLIC_KEYS)} Supabase JWKS key(s)")
    except Exception as e:
        logger.warning(f"⚠️  Could not load Supabase JWKS (will use JWT secret fallback): {e}")

# Load keys eagerly at module import time
_load_jwks()


# ── Supabase JWT verification ─────────────────────────────────────────────────
def decode_supabase_token(token: str) -> Dict[str, Any]:
    """
    Verify a Supabase-issued JWT.
    - Tries ES256 via JWKS public key first (newer Supabase projects).
    - Falls back to HS256 with the JWT secret (legacy).
    """
    # 1. Try ES256 via JWKS
    if _JWKS_PUBLIC_KEYS:
        try:
            # Peek at the token header to get the kid
            unverified_header = pyjwt.get_unverified_header(token)
            kid = unverified_header.get("kid", "default")
            # Use the matching key or the first available key
            public_key = _JWKS_PUBLIC_KEYS.get(kid) or next(iter(_JWKS_PUBLIC_KEYS.values()))
            payload = pyjwt.decode(
                token,
                public_key,
                algorithms=["ES256"],
                options={"verify_aud": False},
            )
            return payload
        except pyjwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except pyjwt.InvalidTokenError as exc:
            logger.debug(f"ES256 decode failed, trying HS256 fallback: {exc}")

    # 2. Fallback: HS256 with JWT secret (older Supabase / local dev)
    secret = settings.supabase_jwt_secret
    if secret:
        try:
            payload = pyjwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            return payload
        except pyjwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except pyjwt.InvalidTokenError:
            pass

    logger.error("JWT verification failed with both ES256 and HS256")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ── User lookup / upsert ──────────────────────────────────────────────────────
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower().strip()).first()


def get_user_by_supabase_id(db: Session, supabase_id: str) -> Optional[User]:
    return db.query(User).filter(User.supabase_id == supabase_id).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def upsert_supabase_user(db: Session, supabase_id: str, email: str) -> User:
    """
    Find or create a local User record for the given Supabase user.
    Called on every authenticated request via get_current_user.
    """
    # 1. Lookup by supabase_id (fastest path for returning users)
    user = get_user_by_supabase_id(db, supabase_id)
    if user:
        return user

    # 2. Lookup by email (handles users who registered before Supabase migration)
    user = get_user_by_email(db, email)
    if user:
        user.supabase_id = supabase_id
        db.commit()
        db.refresh(user)
        logger.info(f"Linked existing user {email} to Supabase ID {supabase_id}")
        return user

    # 3. Create new user record
    user = User(
        email=email.lower().strip(),
        supabase_id=supabase_id,
        plan="free",
        trial_end_date=datetime.utcnow() + timedelta(days=7),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"New Supabase user created in local DB: {email}")
    return user


# ── FastAPI dependency — current user ─────────────────────────────────────────
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_supabase_token(credentials.credentials)

    supabase_id: str = payload.get("sub", "")
    email: str = payload.get("email", "")

    if not supabase_id or not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = upsert_supabase_user(db, supabase_id, email)

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is inactive")

    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns None instead of raising if no valid token is provided."""
    if not credentials or not credentials.credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


def require_plan(min_plan: str):
    """Dependency factory — raises 403 if user's plan is below minimum."""
    plan_levels = {"free": 0, "pro": 1, "elite": 2}

    def _check(user: User = Depends(get_current_user)):
        if plan_levels.get(user.plan, 0) < plan_levels.get(min_plan, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires a {min_plan.title()} plan or higher.",
            )
        return user

    return _check
