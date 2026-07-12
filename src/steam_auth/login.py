"""Steam web login flow (IAuthenticationService) using curl-cffi."""

import base64
import secrets
import time
from typing import NamedTuple

import rsa
from curl_cffi import requests

API_BASE = 'https://api.steampowered.com/IAuthenticationService'

# EAuthSessionGuardType
GUARD_NONE = 1
GUARD_EMAIL_CODE = 2
GUARD_DEVICE_CODE = 3
GUARD_DEVICE_CONFIRMATION = 4

POLL_TIMEOUT_SECONDS = 120

ERESULT_MESSAGES = {
    '5': 'invalid password',
    '84': 'too many login attempts; wait a few minutes',
    '88': 'incorrect Steam Guard code',
}


class SteamLoginError(Exception):
    pass


class LoginResult(NamedTuple):
    session: requests.Session
    steam_id: str
    refresh_token: str


def login(username: str, password: str) -> LoginResult:
    """Authenticates on Steam and returns the session with the web domains' cookies."""
    session = requests.Session(impersonate='chrome')
    encrypted_password, timestamp = _encrypt_password(session, username, password)
    auth = _begin_auth_session(session, username, encrypted_password, timestamp)
    _handle_steam_guard(session, auth)
    refresh_token = _poll_refresh_token(session, auth)
    steam_id = _finalize_login(session, refresh_token)
    return LoginResult(session, steam_id, refresh_token)


def is_session_valid(session: requests.Session) -> bool:
    """When logged out, /account/ redirects to the login page."""
    response = session.get('https://store.steampowered.com/account/', allow_redirects=False)
    return response.status_code == 200


def _api_response(response) -> dict:
    eresult = response.headers.get('x-eresult', '1')
    if eresult != '1':
        detail = ERESULT_MESSAGES.get(eresult, f'EResult {eresult}')
        raise SteamLoginError(f'Steam refused the request: {detail}')
    return response.json()['response']


def _encrypt_password(session: requests.Session, username: str, password: str) -> tuple[str, str]:
    response = session.get(f'{API_BASE}/GetPasswordRSAPublicKey/v1/', params={'account_name': username})
    data = _api_response(response)
    key = rsa.PublicKey(int(data['publickey_mod'], 16), int(data['publickey_exp'], 16))
    encrypted = base64.b64encode(rsa.encrypt(password.encode('utf-8'), key)).decode()
    return encrypted, data['timestamp']


def _begin_auth_session(session: requests.Session, username: str, encrypted_password: str, timestamp: str) -> dict:
    response = session.post(
        f'{API_BASE}/BeginAuthSessionViaCredentials/v1/',
        data={
            'account_name': username,
            'encrypted_password': encrypted_password,
            'encryption_timestamp': timestamp,
            'persistence': '1',
            'website_id': 'Community',
        },
    )
    auth = _api_response(response)
    if 'client_id' not in auth:
        raise SteamLoginError('login refused; check STEAM_USERNAME and STEAM_PASSWORD')
    return auth


def _handle_steam_guard(session: requests.Session, auth: dict) -> None:
    confirmations = {c['confirmation_type'] for c in auth.get('allowed_confirmations', [])}
    if not confirmations or GUARD_NONE in confirmations:
        return

    if GUARD_DEVICE_CODE in confirmations or GUARD_EMAIL_CODE in confirmations:
        if GUARD_DEVICE_CODE in confirmations:
            code_type, source = GUARD_DEVICE_CODE, 'Steam app'
        else:
            code_type, source = GUARD_EMAIL_CODE, 'email'
        try:
            code = input(f'Steam Guard code ({source}): ').strip()
        except EOFError:
            raise SteamLoginError('Steam Guard asked for a code; run in an interactive terminal') from None
        response = session.post(
            f'{API_BASE}/UpdateAuthSessionWithSteamGuardCode/v1/',
            data={
                'client_id': auth['client_id'],
                'steamid': auth['steamid'],
                'code': code,
                'code_type': str(code_type),
            },
        )
        _api_response(response)
    elif GUARD_DEVICE_CONFIRMATION in confirmations:
        print('Confirm the login in the Steam mobile app...')
    else:
        raise SteamLoginError(f'unsupported Steam Guard confirmation type: {confirmations}')


def _poll_refresh_token(session: requests.Session, auth: dict) -> str:
    interval = float(auth.get('interval', 5))
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = session.post(
            f'{API_BASE}/PollAuthSessionStatus/v1/',
            data={'client_id': auth['client_id'], 'request_id': auth['request_id']},
        )
        status = _api_response(response)
        if status.get('refresh_token'):
            return status['refresh_token']
        time.sleep(interval)
    raise SteamLoginError('timed out waiting for the login confirmation')


def _finalize_login(session: requests.Session, refresh_token: str) -> str:
    # The sessionid is client-generated, just like the Steam site does in the browser.
    session_id = secrets.token_hex(12)
    response = session.post(
        'https://login.steampowered.com/jwt/finalizelogin',
        data={
            'nonce': refresh_token,
            'sessionid': session_id,
            'redir': 'https://steamcommunity.com/login/home/?goto=',
        },
        headers={
            'Origin': 'https://steamcommunity.com',
            'Referer': 'https://steamcommunity.com/',
        },
    )
    data = response.json()
    if 'steamID' not in data:
        raise SteamLoginError(f'finalizelogin falhou: {data}')

    steam_id = data['steamID']
    for transfer in data['transfer_info']:
        session.post(transfer['url'], data={**transfer['params'], 'steamID': steam_id})
    for domain in ('steamcommunity.com', 'store.steampowered.com'):
        session.cookies.set('sessionid', session_id, domain=domain, path='/')
    return steam_id
