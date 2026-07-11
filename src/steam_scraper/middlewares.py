"""Project middlewares."""

import logging
from urllib.parse import urlsplit

from scrapy.http.request import Request
from scrapy.http.response import Response

from steam_auth import renew_session
from steam_auth.storage import SESSION_FILE, load_cookies

logger = logging.getLogger(__name__)

STEAM_DOMAINS = ('steamcommunity.com', 'steampowered.com', 'steam.tv')
REDIRECT_STATUSES = (301, 302, 303, 307, 308)


class SteamSessionMiddleware:
    """Injects the saved session cookies into every Steam request and, when a
    response indicates an invalid session (redirect to /login or 401), redoes
    the login via steam_auth, saves the new session and retries the original
    request.

    There is no retry limit: if the new session also fails, the cycle repeats
    until the login itself fails (e.g. Steam rate limit), which drops the
    request with SteamLoginError.

    Must run with priority > 600 to intercept the invalid-session 302 before
    RedirectMiddleware follows it to the login page.
    """

    def __init__(self) -> None:
        self._session_version = 0
        self._domain_cookies: dict[str, dict[str, str]] = {}
        if not SESSION_FILE.exists():
            self._renew('nenhuma sessão salva encontrada')

    def process_request(self, request: Request, spider) -> None:
        host = urlsplit(request.url).netloc
        if not self._is_steam_host(host):
            return None

        request.meta['steam_session_version'] = self._session_version
        if isinstance(request.cookies, dict):
            # Session cookies take precedence; other spider-set cookies are kept.
            request.cookies = {**request.cookies, **self._cookies_for(host)}
        return None

    def process_response(self, request: Request, response: Response, spider) -> Response | Request:
        host = urlsplit(request.url).netloc
        if not self._is_steam_host(host) or not self._is_auth_failure(response):
            return response

        if request.meta.get('steam_session_version') == self._session_version:
            self._renew(f'{response.status} em {request.url}')

        retries = request.meta.get('steam_session_retries', 0) + 1
        request.meta['steam_session_retries'] = retries
        logger.info('Repetindo %s com a nova sessão (tentativa %d)', request.url, retries)
        return request.replace(dont_filter=True)

    def _renew(self, reason: str) -> None:
        logger.info('Refazendo a sessão Steam (%s)...', reason)
        renew_session()
        self._domain_cookies.clear()
        self._session_version += 1

    def _cookies_for(self, host: str) -> dict[str, str]:
        if host not in self._domain_cookies:
            self._domain_cookies[host] = load_cookies(host)
        return self._domain_cookies[host]

    @staticmethod
    def _is_steam_host(host: str) -> bool:
        return any(host == domain or host.endswith('.' + domain) for domain in STEAM_DOMAINS)

    @staticmethod
    def _is_auth_failure(response: Response) -> bool:
        if response.status == 401:
            return True
        if response.status in REDIRECT_STATUSES:
            location = response.headers.get('Location') or b''
            return urlsplit(location.decode()).path.startswith('/login')
        return False
