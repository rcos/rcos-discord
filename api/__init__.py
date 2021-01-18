import aiohttp
import jwt
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ['API_URL']
JWT_SECRET = os.environ['POSTGREST_JWT_SECRET']

# Create JSON Web Token to authenticate Postgrest
encoded_jwt = jwt.encode({'role': 'api_user'}, JWT_SECRET,
                         algorithm='HS256')

api = aiohttp.ClientSession(headers={
    'Authorization': 'Bearer ' + encoded_jwt
})
