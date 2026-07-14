"""Application settings, loaded from the environment and the repo-root .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / '.env'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='STEAM_', env_file=ENV_FILE, extra='ignore')

    username: str = ''
    password: str = ''


settings = Settings()
