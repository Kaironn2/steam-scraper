"""Collects game info (nothing user-specific) from profiles' "All games" tab.

Pass one or more usernames and the spider yields the union of their
libraries, deduplicated by appid — e.g. the members of a Steam Family to map
the games the family has access to.

Usage:
    uv run scrapy crawl users_games -a usernames=user1,user2 -O games.json
    uv run scrapy crawl users_games -a usernames=user1 -a language=ptbr
"""

import json
from collections.abc import AsyncIterator, Generator
from typing import Any

import scrapy
from scrapy.http import Response

from steam_scraper.items import Game

RENDER_CONTEXT_PREFIX = 'window.SSR.renderContext=JSON.parse('


class UsersGamesSpider(scrapy.Spider):
    name = 'users_games'

    def __init__(self, usernames: str = '', **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.usernames = [name.strip() for name in usernames.split(',') if name.strip()]
        if not self.usernames:
            raise ValueError('usernames required: scrapy crawl users_games -a usernames=user1,user2')
        self.seen_appids: set[int] = set()

    async def start(self) -> AsyncIterator[Any]:
        for username in self.usernames:
            yield scrapy.Request(
                url=f'https://steamcommunity.com/id/{username}/games/?tab=all',
                callback=self.parse,
                cb_kwargs={'username': username},
            )

    def parse(self, response: Response, username: str) -> Generator[Game, Any, None]:
        queries = self._render_context_queries(response)
        games = next((q['state']['data'] for q in queries if q['queryKey'][0] == 'OwnedGames'), None)
        if games is None:
            self.logger.error('Games list not found for %r (private or nonexistent profile?)', username)
            return

        achievements = {
            query['queryKey'][2]: query['state']['data']
            for query in queries
            if query['queryKey'][0] == 'AchievementProgress'
        }

        new_games = 0
        for game in games:
            appid = game['appid']
            if appid in self.seen_appids:
                continue
            self.seen_appids.add(appid)
            new_games += 1

            progress = achievements.get(appid) or {}
            yield Game(
                appid=appid,
                name=game['name'],
                achievements_total=progress.get('total'),
            )

        self.logger.info('%s: %d games on the all tab, %d new', username, len(games), new_games)

    def _render_context_queries(self, response: Response) -> list[dict[str, Any]]:
        """The React Query state embedded in window.SSR.renderContext, where
        the page ships the games list (OwnedGames query) and the per-game
        achievement counts (AchievementProgress queries)."""
        start = response.text.find(RENDER_CONTEXT_PREFIX)
        if start == -1:
            return []

        payload, _ = json.JSONDecoder().raw_decode(response.text, start + len(RENDER_CONTEXT_PREFIX))
        render_context = json.loads(payload)
        query_data = render_context.get('queryData')

        if not query_data:
            return []

        return json.loads(query_data)['queries']
