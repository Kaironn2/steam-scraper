BOT_NAME = 'steam_scraper'

SPIDER_MODULES = ['steam_scraper.spiders']
NEWSPIDER_MODULE = 'steam_scraper.spiders'

ROBOTSTXT_OBEY = True

# Session priority > 600: intercepts the invalid-session 302 before RedirectMiddleware.
# Language priority > session: the Steam_Language cookie must win over session cookies.
DOWNLOADER_MIDDLEWARES = {
    'steam_scraper.middlewares.SteamSessionMiddleware': 650,
    'steam_scraper.middlewares.SteamLanguageMiddleware': 660,
}

FEED_EXPORT_ENCODING = 'utf-8'
