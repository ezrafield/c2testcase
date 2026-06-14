from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    log_level: str = "info"


def load_settings() -> Settings:
    return Settings(
        app_env=getenv("APP_ENV", "development"),
        log_level=getenv("LOG_LEVEL", "info"),
    )
