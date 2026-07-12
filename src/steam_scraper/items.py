"""Project items — https://docs.scrapy.org/en/latest/topics/items.html"""

import scrapy


class Game(scrapy.Item):
    appid = scrapy.Field()
    name = scrapy.Field()
    achievements_total = scrapy.Field()
