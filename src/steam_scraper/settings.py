BOT_NAME = 'steam_scraper'

SPIDER_MODULES = ['steam_scraper.spiders']
NEWSPIDER_MODULE = 'steam_scraper.spiders'

ROBOTSTXT_OBEY = True

# Priority > 600: intercepts the invalid-session 302 before RedirectMiddleware.
DOWNLOADER_MIDDLEWARES = {
    'steam_scraper.middlewares.SteamSessionMiddleware': 650,
}

FEED_EXPORT_ENCODING = 'utf-8'
