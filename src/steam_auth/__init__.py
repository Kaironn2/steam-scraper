"""Obtains and persists the Steam web session via curl-cffi."""

import os

from dotenv import load_dotenv

from steam_auth.login import LoginResult, SteamLoginError, login
from steam_auth.storage import save_session


def renew_session() -> LoginResult:
    """Logs in with the credentials from .env and saves the session."""
    load_dotenv()
    username = os.getenv('STEAM_USERNAME')
    password = os.getenv('STEAM_PASSWORD')
    if not username or not password:
        raise SteamLoginError('Set STEAM_USERNAME and STEAM_PASSWORD in .env')

    result = login(username, password)
    save_session(result)
    return result
