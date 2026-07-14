"""Obtains and persists the Steam web session via curl-cffi."""

from core.config import settings
from steam_auth.login import LoginResult, SteamLoginError, login
from steam_auth.storage import save_session


def renew_session() -> LoginResult:
    """Logs in with the credentials from the settings and saves the session."""
    if not settings.username or not settings.password:
        raise SteamLoginError('Set STEAM_USERNAME and STEAM_PASSWORD in .env')

    result = login(settings.username, settings.password)
    save_session(result)
    return result
