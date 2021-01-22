from typing import Dict, Optional
import requests
import os
import jwt

from requests.exceptions import HTTPError

API_URL = os.environ.get('RCOS_API_URL')
JWT_SECRET = os.environ["POSTGREST_JWT_SECRET"]


# Create JSON Web Token to authenticate Postgrest
encoded_jwt = jwt.encode({"role": "api_user"}, JWT_SECRET,
                         algorithm="HS256")


api = requests.Session()
api.headers['Authorization'] = 'Bearer ' + encoded_jwt


def create_or_update_user(username: str, user: Dict) -> Optional[Dict]:
    r = api.put(f'{API_URL}/users', params={
        'username': 'eq.' + username
    }, json=user, headers={
        'Prefer': 'return=representation'
    })
    try:
        r.raise_for_status()
    except HTTPError as err:
        print(err)
        print(err.response.json())
        return None
    return r.json()[0]


def fetch_user(username: str) -> Optional[Dict]:
    r = api.get(API_URL + '/users', params={
        'username': 'eq.' + username
    }, headers={
        'Accept': 'application/vnd.pgrst.object+json'
    })
    try:
        r.raise_for_status()
    except HTTPError as err:
        print(err)
        print(err.response.json())
        return None
    return r.json()


def fetch_user_discord_account(username: str) -> Optional[Dict]:
    r = api.get(f'{API_URL}/user_accounts', params={
        'username': 'eq.' + username,
        'type': 'eq.discord'
    }, headers={
        'Authentication': 'Bearer ' + encoded_jwt,
        'Accept': 'application/vnd.pgrst.object+json'
    })
    try:
        r.raise_for_status()
    except HTTPError as err:
        print(err)
        print(err.response.json())
        return None
    return r.json()


def create_or_update_user_discord_account(username: str, discord_user_id: str):
    r = api.put(f'{API_URL}/user_accounts', params={
        'username': 'eq.' + username,
        'type': 'eq.discord'
    }, json={
        'username': username,
        'type': 'discord',
        'account_id': discord_user_id
    }, headers={
        'Prefer': 'return=representation'
    })
    try:
        r.raise_for_status()
    except HTTPError as err:
        print(err)
        print(err.response.json())
        return None
    return r.json()


def delete_user_discord_account(username: str):
    r = api.delete(f'{API_URL}/user_accounts', params={
        'username': 'eq.' + username,
        'type': 'eq.discord'
    }, headers={
        'Prefer': 'return=representation'
    })
    try:
        r.raise_for_status()
    except HTTPError as err:
        print(err)
        print(err.response.json())
        return None
    return r.json()
