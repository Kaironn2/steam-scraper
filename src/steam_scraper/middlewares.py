"""Project middlewares."""

import logging
from urllib.parse import urlsplit

from scrapy.http.request import Request
from scrapy.http.response import Response

from steam_auth import renew_session
from steam_auth.storage import SESSION_FILE, load_cookies
from steam_scraper.languages import DEFAULT_LANGUAGE, resolve_language

logger = logging.getLogger(__name__)

STEAM_DOMAINS = ('steamcommunity.com', 'steampowered.com', 'steam.tv')
REDIRECT_STATUSES = (301, 302, 303, 307, 308)


def _is_steam_host(host: str) -> bool:
    return any(host == domain or host.endswith('.' + domain) for domain in STEAM_DOMAINS)


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
            self._renew('no saved session found')

    def process_request(self, request: Request, spider) -> None:
        host = urlsplit(request.url).netloc
        if not _is_steam_host(host):
            return None

        request.meta['steam_session_version'] = self._session_version
        if isinstance(request.cookies, dict):
            # Session cookies take precedence; other spider-set cookies are kept.
            request.cookies = {**request.cookies, **self._cookies_for(host)}
        return None

    def process_response(self, request: Request, response: Response, spider) -> Response | Request:
        host = urlsplit(request.url).netloc
        if not _is_steam_host(host) or not self._is_auth_failure(response):
            return response

        if request.meta.get('steam_session_version') == self._session_version:
            self._renew(f'{response.status} at {request.url}')

        retries = request.meta.get('steam_session_retries', 0) + 1
        request.meta['steam_session_retries'] = retries
        logger.info('Retrying %s with the new session (attempt %d)', request.url, retries)
        return request.replace(dont_filter=True)

    def _renew(self, reason: str) -> None:
        logger.info('Renewing the Steam session (%s)...', reason)
        renew_session()
        self._domain_cookies.clear()
        self._session_version += 1

    def _cookies_for(self, host: str) -> dict[str, str]:
        if host not in self._domain_cookies:
            self._domain_cookies[host] = load_cookies(host)
        return self._domain_cookies[host]

    @staticmethod
    def _is_auth_failure(response: Response) -> bool:
        if response.status == 401:
            return True
        if response.status in REDIRECT_STATUSES:
            location = response.headers.get('Location') or b''
            return urlsplit(location.decode()).path.startswith('/login')
        return False


class SteamLanguageMiddleware:
    """Applies the spider's language to every Steam request, via the
    Steam_Language cookie and the Accept-Language header.

    The language comes from the spider's `language` attribute — set with
    `-a language=<abbreviation>` (see steam_scraper.languages); when absent,
    DEFAULT_LANGUAGE is used. Spiders need no extra code.

    Must run with priority > SteamSessionMiddleware so the language cookie is
    set after the session cookies are merged in, and therefore always wins.
    """

    def process_request(self, request: Request, spider) -> None:
        if not _is_steam_host(urlsplit(request.url).netloc):
            return None

        language = resolve_language(getattr(spider, 'language', DEFAULT_LANGUAGE))
        request.headers['Accept-Language'] = language.accept_language
        if isinstance(request.cookies, dict):
            request.cookies['Steam_Language'] = language.code
        return None
