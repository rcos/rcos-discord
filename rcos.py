from typing import Dict, Optional
import requests
import os

from requests.exceptions import HTTPError

api_base_url = 'https://rcos-api.herokuapp.com/api/v1'

headers = {
    'api_key': os.environ['RCOS_API_KEY']
}

def upser_user(username: str, user: Dict) -> Optional[Dict]:
    r = requests.put(f'{api_base_url}/users/{username}', json={
        **user,
        'is_rpi': True,
        'is_faculty': False
    }, headers=headers)
    print(r.json())
    try:
        r.raise_for_status()
    except HTTPError as err:
        print(err)
        return None
    return r.json()

def fetch_user(username: str) -> Optional[Dict]:
    r = requests.get(api_base_url + '/users/' + username, headers=headers)
    try:
        r.raise_for_status()
    except HTTPError as err:
        print(err)
        return None
    return r.json()

def fetch_user_discord_account(username: str) -> Optional[Dict]:
    r = requests.get(f'{api_base_url}/users/{username}/accounts/discord', headers=headers)
    try:
        r.raise_for_status()
    except HTTPError as err:
        return None
    return r.json()

def upsert_user_discord_account(username: str, discord_user_id: str):
    r = requests.put(f'{api_base_url}/users/{username}/accounts/discord', json={ 'account_id': discord_user_id }, headers=headers)
    try:
        r.raise_for_status()
    except HTTPError as err:
        return None
    return r.json()

def delete_user_discord_account(username: str):
    r = requests.delete(f'{api_base_url}/users/{username}/accounts/discord', headers=headers)
    try:
        r.raise_for_status()
    except HTTPError as err:
        return None
    return r.json()