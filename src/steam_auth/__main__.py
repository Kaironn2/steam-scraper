import sys

from steam_auth import renew_session
from steam_auth.login import SteamLoginError, is_session_valid
from steam_auth.storage import SESSION_FILE


def main() -> None:
    try:
        result = renew_session()
    except SteamLoginError as exc:
        sys.exit(f'Falha no login: {exc}')

    status = 'válida' if is_session_valid(result.session) else 'NÃO validada'
    print(f'Sessão {status} salva em {SESSION_FILE} (steam_id={result.steam_id})')


if __name__ == '__main__':
    main()
