"""Configuration read from environment variables (12-factor style).

Nothing secret is stored in the code or the repository. The application fails fast at
start-up when staging or production is misconfigured, instead of running insecurely.
"""
import os
from dataclasses import dataclass

ENVIRONMENTS = ("development", "staging", "production")
MIN_API_KEY_LENGTH = 16


class ConfigError(Exception):
    """Raised when the environment configuration is missing or unsafe."""


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    db_path: str = "expenses.db"
    log_level: str = "INFO"
    api_key: str = ""
    max_body_bytes: int = 10_000

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        env = os.environ if env is None else env
        settings = cls(
            environment=env.get("APP_ENV", "development").strip().lower(),
            db_path=env.get("DB_PATH", "expenses.db").strip(),
            log_level=env.get("LOG_LEVEL", "INFO").strip().upper(),
            api_key=env.get("API_KEY", "").strip(),
            max_body_bytes=_int(env.get("MAX_BODY_BYTES", "10000"), "MAX_BODY_BYTES"),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.environment not in ENVIRONMENTS:
            raise ConfigError(f"APP_ENV must be one of {ENVIRONMENTS}, got {self.environment!r}")
        if self.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise ConfigError(f"LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR, got {self.log_level!r}")
        if not self.db_path:
            raise ConfigError("DB_PATH must not be empty")
        if self.max_body_bytes < 100:
            raise ConfigError("MAX_BODY_BYTES must be at least 100")
        if self.environment in ("staging", "production") and len(self.api_key) < MIN_API_KEY_LENGTH:
            raise ConfigError(
                f"API_KEY must be set and at least {MIN_API_KEY_LENGTH} characters when "
                f"APP_ENV={self.environment}")


def _int(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {value!r}")
