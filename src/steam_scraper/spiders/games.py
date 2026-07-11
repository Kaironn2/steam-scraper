"""Example spider: counts the logged-in account's games.

Authentication is SteamSessionMiddleware's responsibility — the spider does
not manage cookies.
"""

import re
from collections.abc import AsyncIterator, Generator
from typing import Any

import scrapy
from scrapy.http import Response


class GamesSpider(scrapy.Spider):
    name = 'games'
    username = 'kaironn1'

    async def start(self) -> AsyncIterator[Any]:
        url = f'https://steamcommunity.com/id/{self.username}/games/?tab=all'
        yield scrapy.Request(url=url)

    def parse(self, response: Response) -> Generator[dict[str, Any], Any, None]:
        appids = set(re.findall(r'"appid\\*"?:(\d+)', response.text))
        yield {'username': self.username, 'total_games': len(appids)}
