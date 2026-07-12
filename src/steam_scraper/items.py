"""Project items — https://docs.scrapy.org/en/latest/topics/items.html"""

import scrapy


class Game(scrapy.Item):
    appid = scrapy.Field()
    name = scrapy.Field()
    achievements_total = scrapy.Field()


class Achievement(scrapy.Item):
    username = scrapy.Field()
    appid = scrapy.Field()
    game = scrapy.Field()
    title = scrapy.Field()
    description = scrapy.Field()
    unlocked = scrapy.Field()
    unlock_time = scrapy.Field()
    progress_current = scrapy.Field()
    progress_total = scrapy.Field()
    language = scrapy.Field()
