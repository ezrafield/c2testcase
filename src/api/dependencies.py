from src.core.config import Settings, load_settings


def get_settings() -> Settings:
    return load_settings()
