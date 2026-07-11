"""JSON session persistence, shared between the login and the spiders."""

import json
from pathlib import Path

from steam_auth.login import LoginResult

SESSION_FILE = Path(__file__).resolve().parents[2] / 'sessions' / 'steam.json'


def save_session(result: LoginResult, path: Path = SESSION_FILE) -> Path:
    cookies = [
        {
            'name': cookie.name,
            'value': cookie.value,
            'domain': cookie.domain,
            'path': cookie.path,
            'secure': bool(cookie.secure),
            'expires': cookie.expires,
        }
        for cookie in result.session.cookies.jar
    ]
    payload = {
        'steam_id': result.steam_id,
        'refresh_token': result.refresh_token,
        'cookies': cookies,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return path


def load_cookies(domain: str, path: Path = SESSION_FILE) -> dict[str, str]:
    """The domain's cookies as name→value, in the scrapy.Request(cookies=...) format."""
    payload = json.loads(path.read_text(encoding='utf-8'))
    cookies = {}
    for cookie in payload['cookies']:
        cookie_domain = cookie['domain'].lstrip('.')
        if domain == cookie_domain or domain.endswith('.' + cookie_domain):
            cookies[cookie['name']] = cookie['value']
    return cookies
