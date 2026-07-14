"""Collects a user's achievements for every game in a users_games output file.

Receives a username and the JSON produced by the users_games spider, visits
the profile's achievements page of each game that has achievements and yields
one item per game with its achievements nested, locked ones included. Locked
*hidden* achievements can't be collected individually — Steam only shows them
aggregated in a "+N hidden achievements remaining" row; the spider logs how
many were omitted.

Usage:
    uv run scrapy crawl user_achievements -a username=user1 -a games_file=games.json -O achievements.json
    uv run scrapy crawl user_achievements -a username=user1 -a games_file=games.json -a language=ptbr
"""

import re
from collections.abc import AsyncIterator, Generator
from datetime import datetime
from pathlib import Path
from typing import Any

import scrapy
from pydantic import TypeAdapter
from scrapy.http import Response

from steam_scraper.items import Achievement, Game, GameAchievements
from steam_scraper.languages import DEFAULT_LANGUAGE, resolve_language

# "21 Dec, 2024 @ 8:08pm" / "12 Jul @ 1:23pm" (en) — "21/dez./2024 às 20:08" / "20 de jan. às 5:45" (ptbr).
# Steam omits the year when the achievement was unlocked in the current year.
UNLOCK_TIME_RE = re.compile(
    r'(\d{1,2})[\s/](?:de\s+)?(\w{3,4})\.?[,/]?\s*(?:de\s+)?(\d{4})?\s*(?:@|às)\s*(\d{1,2}):(\d{2})\s*([ap]m)?',
    re.IGNORECASE,
)

MONTHS = {
    'jan': 1,
    'feb': 2,
    'fev': 2,
    'mar': 3,
    'apr': 4,
    'abr': 4,
    'may': 5,
    'mai': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'ago': 8,
    'sep': 9,
    'set': 9,
    'oct': 10,
    'out': 10,
    'nov': 11,
    'dec': 12,
    'dez': 12,
}


class UserAchievementsSpider(scrapy.Spider):
    name = 'user_achievements'

    # One request per game in the library is enough volume to trip Steam's
    # rate limiting at Scrapy's default pace.
    custom_settings = {
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 0.5,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 4.0,
    }

    def __init__(self, username: str = '', games_file: str = '', **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if not username or not games_file:
            raise ValueError(
                'username and games_file required: '
                'scrapy crawl user_achievements -a username=user1 -a games_file=games.json'
            )
        self.username = username
        self.games: list[Game] = TypeAdapter(list[Game]).validate_json(Path(games_file).read_bytes())
        self._warned_unlock_format = False

    async def start(self) -> AsyncIterator[Any]:
        games = [game for game in self.games if game.achievements_total != 0]
        self.logger.info('%d of %d games have achievements', len(games), len(self.games))

        for game in games:
            yield scrapy.Request(
                url=f'https://steamcommunity.com/id/{self.username}/stats/{game.appid}/?tab=achievements',
                callback=self.parse,
                cb_kwargs={'game': game},
            )

    def parse(self, response: Response, game: Game) -> Generator[Any, Any, None]:
        rows = response.xpath('//div[contains(@class, "achieveRow")]')
        if not rows:
            request = response.request
            if request and '/stats/' in response.url and 'tab=achievements' not in response.url:
                # Games with a vanity stats URL redirect there (e.g. /stats/730 ->
                # /stats/CSGO) dropping the query string; ask for the tab again.
                yield request.replace(url=response.urljoin('?tab=achievements'))
            else:
                self.logger.warning('%s: no achievements page at %s (never played?)', game.name, response.url)
            return

        hidden = 0
        achievements: list[Achievement] = []
        for row in rows:
            hidden_box = row.xpath('./div[@class="achieveHiddenBox"]/span/text()').get()
            if hidden_box is not None:
                # Locked hidden achievements only appear aggregated: "+N remaining".
                hidden += int(re.sub(r'\D', '', hidden_box) or 0)
                continue

            # contains(): rows with a progress bar use class="achieveTxt withProgress"
            title = _normalize(row.xpath('.//div[contains(@class, "achieveTxt")]/h3/text()').get())
            if title is None:
                self.logger.error('%s: achievement row without title at %s, skipping', game.name, response.url)
                continue

            unlock_text = row.xpath('.//div[@class="achieveUnlockTime"]/text()').get()
            progress_current, progress_total = _parse_progress(
                row.xpath('.//div[contains(@class, "progressText")]/text()').get()
            )

            achievements.append(
                Achievement(
                    title=title,
                    description=_normalize(row.xpath('.//div[contains(@class, "achieveTxt")]/h5/text()').get()),
                    unlocked=unlock_text is not None,
                    unlock_time=self._parse_unlock_time(unlock_text),
                    progress_current=progress_current,
                    progress_total=progress_total,
                )
            )

        if hidden:
            self.logger.info('%s: %d locked hidden achievements are not listed by Steam', game.name, hidden)

        yield GameAchievements(
            username=self.username,
            appid=game.appid,
            game=game.name,
            achievements_total=game.achievements_total,
            language=resolve_language(getattr(self, 'language', DEFAULT_LANGUAGE)).code,
            achievements=achievements,
        )

    def _parse_unlock_time(self, text: str | None) -> str | None:
        """The unlock time as ISO 8601: 'Unlocked 21 Dec, 2024 @ 8:08pm' -> '2024-12-21T20:08:00'."""
        if text is None:
            return None

        match = UNLOCK_TIME_RE.search(text)
        month = MONTHS.get(match[2].lower()[:3]) if match else None
        if match and month:
            day, _, year, hour, minute, meridiem = match.groups()
            hour = int(hour)
            if meridiem:
                hour = hour % 12 + (12 if meridiem.lower() == 'pm' else 0)
            try:
                return datetime(
                    int(year) if year else datetime.now().year, month, int(day), hour, int(minute)
                ).isoformat()
            except ValueError:
                pass

        if not self._warned_unlock_format:
            self._warned_unlock_format = True
            self.logger.warning('Unrecognized unlock time format %r; unlock_time will be null', text.strip())
        return None


def _normalize(text: str | None) -> str | None:
    """Replaces the typographic characters Steam uses with their ASCII equivalents."""
    if text is None:
        return None
    return text.replace('\u00a0', ' ').replace('\u2019', "'").strip()  # non-breaking space, right single quote


def _parse_progress(text: str | None) -> tuple[int | None, int | None]:
    """The progress bar text as numbers: '1,500 / 2,000' -> (1500, 2000)."""
    if text:
        numbers = re.findall(r'\d[\d.,]*', text)
        if len(numbers) == 2:
            current, total = (int(re.sub(r'\D', '', number)) for number in numbers)
            return current, total
    return None, None
