import sys

from steam_auth import renew_session
from steam_auth.login import SteamLoginError, is_session_valid
from steam_auth.storage import SESSION_FILE


def main() -> None:
    try:
        result = renew_session()
    except SteamLoginError as exc:
        sys.exit(f'Login failed: {exc}')

    status = 'Valid' if is_session_valid(result.session) else 'UNVALIDATED'
    print(f'{status} session saved to {SESSION_FILE} (steam_id={result.steam_id})')


if __name__ == '__main__':
    main()
