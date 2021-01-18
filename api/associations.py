from typing import Any, Optional, Union
from . import api, API_URL

async def get_association(source_type: str, target_type: str, target_id: int):
    '''Get a specific chat association
    
    - source_type -  'project' or 'small_group'
    - target_type - check schema
    - target_id - id of target item
    '''
    async with api.get(API_URL + '/chat_associations', params={
        'source_type': 'eq.' + source_type,
        'target_type': 'eq.' + target_type,
        'target_id': 'eq.' + str(target_id)
    }, headers={
        'Accept': 'application/vnd.pgrst.object+json'
    }) as response:
        response.raise_for_status()
        return await response.json()

async def set_association(source_type: str, target_type: str, source_id: Any, target_id: Any):
    '''Insert or update a specific chat association.'''

    async with api.put(API_URL + '/chat_associations', params={
        'source_type': 'eq.' + source_type,
        'target_type': 'eq.' + target_type,
        'source_id': 'eq.' + str(source_id),
    }, json={
        'source_type': source_type,
        'target_type': target_type,
        'source_id': source_id,
        'target_id': target_id
    }, headers={
        'Prefer': 'return=representation'
    }) as response:
        response.raise_for_status()
        return await response.json()[0]

async def list_associations(source_type: Optional[str] = None, target_type: Optional[str] = None, source_id: Optional[Any] = None):
    '''Search for and list associations. At least one parameter must be set.'''
    # Ensure some search keys are present
    if source_type is None and target_type is None and source_id is None:
        raise Exception('Some search parameters must be present')
    
    # Only apply search params that are not-None
    search = locals()
    params = {}
    for key in search.keys():
        if search[key] is not None:
            params[key] = 'eq.' + str(search[key])

    async with api.get(API_URL + '/chat_associations', params=params) as response:
        response.raise_for_status()
        return await response.json()