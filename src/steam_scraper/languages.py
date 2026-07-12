"""Steam language registry, shared by every spider.

Spiders receive the language via `-a language=<abbreviation>` (default: en).
SteamLanguageMiddleware reads the spider's `language` attribute and applies it
to every Steam request — spiders need no extra code.

To support a new language, add an entry to LANGUAGES: the key is the
abbreviation accepted on the command line, `code` is Steam's internal name
(the Steam_Language cookie) and `accept_language` is the Accept-Language
header value.
"""

from typing import NamedTuple


class SteamLanguage(NamedTuple):
    code: str
    accept_language: str


LANGUAGES = {
    'en': SteamLanguage(code='english', accept_language='en-US,en;q=0.9'),
    'ptbr': SteamLanguage(code='brazilian', accept_language='pt-BR,pt;q=0.9'),
}

DEFAULT_LANGUAGE = 'en'


def resolve_language(abbreviation: str) -> SteamLanguage:
    lang = LANGUAGES.get(abbreviation)
    if lang:
        return lang

    supported = ', '.join(LANGUAGES)
    raise ValueError(f"unsupported language '{abbreviation}'; available: {supported}") from None
