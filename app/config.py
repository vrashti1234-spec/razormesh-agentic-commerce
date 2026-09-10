from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    razorpay_key_id: str = Field(..., validation_alias="RAZORPAY_KEY_ID")
    razorpay_key_secret: SecretStr = Field(
        ...,
        validation_alias="RAZORPAY_KEY_SECRET",
    )
    razorpay_test_mode: bool = Field(
        default=True,
        validation_alias="RAZORPAY_TEST_MODE",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
