# steam-scraper

A crawler that retrieves information about the games a Steam user has played
that **we can't obtain through the official API**.

The main use case is **Steam Family**: sometimes a user wants to see data about
games they played through family sharing, but the Steam API only returns the
account's own games. The profile's games tab, on the other hand, shows
everything and that is what this scraper collects.

## Requirements

Since the games tab is only visible when **authenticated**, the application
needs a Steam account to log in. Two important points:

- **The login account cannot have 2FA** (neither email nor the Steam
  Authenticator). The login flow is automated and cannot pass a second-factor
  challenge. **Recommendation:** create a fresh account, without adding 2FA,
  used solely to be able to see the tabs.
- **The target profile must be public.** The application only collects public
  data — private profiles are not visible, not even to the authenticated
  account.

## Installation

Install [uv](https://docs.astral.sh/uv/) and sync the dependencies:

```bash
pip install uv
uv sync
```

Then create a `.env` from the example and fill in the login account's
credentials:

```bash
cp .env.example .env
```

```dotenv
STEAM_USERNAME=your_account
STEAM_PASSWORD=your_password
```

## Usage

Run a spider (login/session is handled automatically):

```bash
uv run scrapy crawl <spider>
```

If you just want to generate/refresh the session manually, without running a
crawl:

```bash
uv run steam-auth
```

### users_games

Collects game info (`appid`, `name`, `achievements_total`) from the
"All games" tab of one or more profiles. The result is the union of the
users' libraries, deduplicated by `appid` — pass the family members'
usernames to map the games available to a Steam Family:

```bash
uv run scrapy crawl users_games -a usernames=user1,user2,user3 -O games.json
```

Private or nonexistent profiles are logged as errors and skipped; the other
usernames are still collected.

### user_achievements

Collects every achievement of one user — locked ones included — for each game
in a `users_games` output file:

```bash
uv run scrapy crawl user_achievements -a username=user1 -a games_file=games.json -O achievements.json
```

Each item is one game of the user (`username`, `appid`, `game`,
`achievements_total`) with the game's achievements nested in `achievements`:
`title`, `description`, the unlock state (`unlocked`, `unlock_time` as
ISO 8601) and, for progress-tracked achievements,
`progress_current`/`progress_total`.

- Games with `achievements_total: 0` are skipped; games without an
  achievements page (never played) are logged and skipped.
- Locked **hidden** achievements cannot be collected individually: Steam only
  shows them aggregated in a "+N hidden achievements remaining" row. The
  spider logs how many were omitted per game — they explain any gap between
  `achievements_total` and the size of `achievements`.

### Language

Every spider accepts `-a language=<code>` (default: `en`):

```bash
uv run scrapy crawl users_games -a usernames=user1 -a language=ptbr
```

| code   | Steam language |
| ------ | -------------- |
| `en`   | english        |
| `ptbr` | brazilian      |

The [`SteamLanguageMiddleware`](src/steam_scraper/middlewares.py) applies the
language to every Steam request (via the `Steam_Language` cookie and the
`Accept-Language` header), so spiders don't need any language-specific code —
the `-a language=...` argument is enough. To support a new language, add an
entry to `LANGUAGES` in
[`src/steam_scraper/languages.py`](src/steam_scraper/languages.py).

## How it works

Login is handled by the [`src/steam_auth/`](src/steam_auth/) module, which
authenticates on Steam via `curl-cffi` (replicating the `IAuthenticationService`
web flow) and saves the session cookies to `sessions/steam.json`.

The spiders **do not manage authentication**. A Scrapy
[`SteamSessionMiddleware`](src/steam_scraper/middlewares.py) injects the saved
session into every request and, when it detects the session has dropped (Steam
responds with a redirect to `/login`), it redoes the login, saves the new
session and retries the original request — a retry mechanism that is transparent
to the spider.

## Structure

```
src/
├── core/              # shared application core
│   └── config.py      # settings loaded from .env via pydantic-settings
├── steam_auth/        # login via curl-cffi + session persistence
│   ├── login.py       # IAuthenticationService flow
│   ├── storage.py     # saves/loads sessions/steam.json
│   └── __main__.py    # `steam-auth` entrypoint
└── steam_scraper/     # Scrapy project
    ├── middlewares.py # SteamSessionMiddleware (session) + SteamLanguageMiddleware
    ├── languages.py   # supported languages registry (-a language=...)
    ├── settings.py
    └── spiders/       # the crawlers
```
