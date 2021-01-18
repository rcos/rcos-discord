import re
from typing import Dict
from api import API_URL, api


async def get_user(username: str):
    '''Get a specific user by username.'''
    async with api.get(API_URL + '/chat_associations', params={
        'username': 'eq.' + username
    }, headers={
        'Accept': 'application/vnd.pgrst.object+json'
    }) as response:
        response.raise_for_status()
        return await response.json()

async def get_user_from_discord_account(discord_user_id: int) -> Dict:
    async with api.get(API_URL + '/user_accounts', params={
        'type': 'eq.discord',
        'account_id': 'eq.' + str(discord_user_id),
        'select': 'user_accounts_pkey:users(*)'
    }, headers={
        'Accept': 'application/vnd.pgrst.object+json'
    }) as response:
        response.raise_for_status()
        return (await response.json())['user_accounts_pkey']