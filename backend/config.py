"""
ANTIGRAVITY — Configuration Management
Loads all environment variables with validation via Pydantic Settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── AI ──────────────────────────────────────────────────────────────────
    gemini_api_key: str = Field(default="", description="Google Gemini API key")

    # ── DATABASE ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/antigravity",
        description="PostgreSQL connection URL",
    )

    # ── JWT AUTH ─────────────────────────────────────────────────────────────
    secret_key: str = Field(
        default_factory=lambda: secrets.token_hex(32),
        description="JWT signing secret",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ── NEWS APIs ─────────────────────────────────────────────────────────────
    newsapi_key: str = Field(default="", description="NewsAPI.org key")
    gnews_api_key: str = Field(default="", description="GNews API key")

    # ── PAYMENTS ─────────────────────────────────────────────────────────────
    razorpay_key_id: str = Field(default="", description="Razorpay Key ID")
    razorpay_key_secret: str = Field(default="", description="Razorpay Key Secret")
    razorpay_webhook_secret: str = Field(default="", description="Razorpay Webhook Secret")

    # ── TELEGRAM ─────────────────────────────────────────────────────────────
    telegram_bot_token: str = Field(default="", description="Telegram Bot Token")
    telegram_pro_channel_id: str = Field(default="", description="Pro channel ID")
    telegram_elite_channel_id: str = Field(default="", description="Elite channel ID")
    admin_telegram_id: str = Field(default="", description="Admin Telegram user ID")

    # ── EMAIL ─────────────────────────────────────────────────────────────────
    resend_api_key: str = Field(default="", description="Resend API key")
    resend_from_email: str = Field(default="digest@antigravity.in")
    resend_from_name: str = Field(default="Antigravity")

    # ── GOOGLE OAUTH ──────────────────────────────────────────────────────────
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")

    # ── SUPABASE ──────────────────────────────────────────────────────────────
    # Get from: Supabase Dashboard → Settings → API → JWT Settings → JWT Secret
    supabase_jwt_secret: str = Field(default="", description="Supabase JWT signing secret for token verification")
    supabase_anon_key: str = Field(default="", description="Supabase anon/public key for API access")

    # ── APP ───────────────────────────────────────────────────────────────────
    backend_url: str = Field(default="http://localhost:8000")
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:3001,http://localhost:3002")
    environment: str = Field(default="development")

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Singleton
settings = Settings()
