import proto.FreeFire_pb2 as FreeFire_pb2
import proto.main_pb2 as main_pb2
import proto.AccountPersonalShow_pb2 as AccountPersonalShow_pb2
import httpx
import asyncio
import json
from google.protobuf import json_format, message
from Crypto.Cipher import AES
import base64

# Constants for encryption and API configuration
MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
RELEASEVERSION = "OB52"
USERAGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
SUPPORTED_REGIONS = ["IND", "BR", "SG", "RU", "ID", "TW", "US", "VN", "TH", "ME", "PK", "CIS", "BD"]

ACCOUNTS = {
    'IND': "uid=3986816049&password=F8FD2A61B00FB662AABA59F137F33BB318E42CC30A99B100223F47BF61FE53DB",
    'SG': "uid=3158350464&password=70EA041FCF79190E3D0A8F3CA95CAAE1F39782696CE9D85C2CCD525E28D223FC",
    'RU': "uid=3301239795&password=DD40EE772FCBD61409BB15033E3DE1B1C54EDA83B75DF0CDD24C34C7C8798475",
    'ID': "uid=3301269321&password=D11732AC9BBED0DED65D0FED7728CA8DFF408E174202ECF1939E328EA3E94356",
    'TW': "uid=3301329477&password=359FB179CD92C9C1A2A917293666B96972EF8A5FC43B5D9D61A2434DD3D7D0BC",
    'US': "uid=3301387397&password=BAC03CCF677F8772473A09870B6228ADFBC1F503BF59C8D05746DE451AD67128",
    'VN': "uid=3301447047&password=044714F5B9284F3661FB09E4E9833327488B45255EC9E0CCD953050E3DEF1F54",
    'TH': "uid=3301470613&password=39EFD9979BD6E9CCF6CBFF09F224C4B663E88B7093657CB3D4A6F3615DDE057A",
    'ME': "uid=3301535568&password=BEC9F99733AC7B1FB139DB3803F90A7E78757B0BE395E0A6FE3A520AF77E0517",
    'PK': "uid=3301828218&password=3A0E972E57E9EDC39DC4830E3D486DBFB5DA7C52A4E8B0B8F3F9DC4450899571",
    'CIS': "uid=3309128798&password=412F68B618A8FAEDCCE289121AC4695C0046D2E45DB07EE512B4B3516DDA8B0F",
    'BR': "uid=3158668455&password=44296D19343151B25DE68286BDC565904A0DA5A5CC5E96B7A7ADBE7C11E07933",
    'BD': "uid=4529143117&password=FF2024_EU0NS_OFFLINEE_CXPFH"
}

async def json_to_proto(json_data: str, proto_message: message.Message) -> bytes:
    """Convert JSON data to a protobuf message and serialize it."""
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

def pad(text: bytes) -> bytes:
    """Pad text to align with AES block size."""
    padding_length = AES.block_size - (len(text) % AES.block_size)
    padding = bytes([padding_length] * padding_length)
    return text + padding

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    """Encrypt data using AES-CBC."""
    aes = AES.new(key, AES.MODE_CBC, iv)
    padded_plaintext = pad(plaintext)
    return aes.encrypt(padded_plaintext)

# Cache helpers (no-op; always miss)
def _get_from_cache(key: str):
    return None

def _set_to_cache(key: str, value: str, ttl: int = 3600):
    return False

def get_jwt_from_cache(region: str):
    """Get JWT token from cache."""
    cache_key = f"jwt_token:{region.upper()}"
    return _get_from_cache(cache_key)

def set_jwt_to_cache(region: str, jwt_data: dict):
    """Cache JWT token for 7 hours."""
    cache_key = f"jwt_token:{region.upper()}"
    jwt_json = json.dumps(jwt_data)
    return _set_to_cache(cache_key, jwt_json, 25200)  # 7 hours = 25200 seconds

def get_access_token_from_cache(region: str):
    """Get access token from cache."""
    cache_key = f"access_token:{region.upper()}"
    return _get_from_cache(cache_key)

def set_access_token_to_cache(region: str, access_token: str, open_id: str):
    """Cache access token for 6 hours."""
    cache_key = f"access_token:{region.upper()}"
    token_data = json.dumps({"access_token": access_token, "open_id": open_id})
    return _set_to_cache(cache_key, token_data, 21600)  # 6 hours = 21600 seconds

def get_player_data_from_cache(uid: str, region: str):
    """Get player data from cache."""
    cache_key = f"player_data:{uid}:{region.upper()}"
    return _get_from_cache(cache_key)

def set_player_data_to_cache(uid: str, region: str, player_data: dict):
    """Cache player data for 1 hour."""
    cache_key = f"player_data:{uid}:{region.upper()}"
    data_json = json.dumps(player_data)
    return _set_to_cache(cache_key, data_json, 3600)  # 1 hour = 3600 seconds

def decode_protobuf(encoded_data: bytes, message_type: message.Message) -> message.Message:
    """Decode protobuf data into a message instance."""
    message_instance = message_type()
    message_instance.ParseFromString(encoded_data)
    return message_instance

async def get_access_token(account, region):
    """Retrieve an access token for the given account with caching."""
    # Try to get from cache first
    cached_token = get_access_token_from_cache(region)
    if cached_token:
        try:
            token_data = json.loads(cached_token)
            print(f"Using cached access token for {region}")
            return token_data.get("access_token", "0"), token_data.get("open_id", "0")
        except:
            pass
    
    # If not in cache, fetch from API
    print(f"Fetching new access token for {region}")
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = account + "&response_type=token&client_type=2&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    headers = {
        'User-Agent': USERAGENT,
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/x-www-form-urlencoded"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload, headers=headers)
        data = response.json()
        access_token = data.get("access_token", "0")
        open_id = data.get("open_id", "0")
        
        # Cache the token
        set_access_token_to_cache(region, access_token, open_id)
        print(f"Cached access token for {region}")
        
        return access_token, open_id

async def create_jwt(region: str):
    """Create a JWT token for authentication with caching."""
    # Try to get JWT from cache first
    cached_jwt = get_jwt_from_cache(region)
    if cached_jwt:
        try:
            jwt_data = json.loads(cached_jwt)
            print(f"Using cached JWT for {region}")
            return jwt_data.get("token"), jwt_data.get("lockRegion"), jwt_data.get("serverUrl")
        except:
            pass
    
    # If not in cache, create new JWT
    print(f"Creating new JWT for {region}")
    account = ACCOUNTS.get(region.upper())
    if not account:
        return None, None, None
    
    access_token, open_id = await get_access_token(account, region)
    json_data = json.dumps({
        "open_id": open_id,
        "open_id_type": "4",
        "login_token": access_token,
        "orign_platform_type": "4"
    })
    encoded_result = await json_to_proto(json_data, FreeFire_pb2.LoginReq())
    payload = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, encoded_result)
    url = "https://loginbp.ggblueshark.com/MajorLogin"
    headers = {
        'User-Agent': USERAGENT,
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream",
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': RELEASEVERSION
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload, headers=headers)
        message = json.loads(json_format.MessageToJson(decode_protobuf(response.content, FreeFire_pb2.LoginRes)))
        token = f"Bearer {message.get('token', '0')}"
        lock_region = message.get("lockRegion", "0")
        server_url = message.get("serverUrl", "0")
        
        # Cache the JWT data
        jwt_data = {
            "token": token,
            "lockRegion": lock_region,
            "serverUrl": server_url
        }
        set_jwt_to_cache(region, jwt_data)
        print(f"Cached JWT for {region}")
        
        return token, lock_region, server_url

async def GetAccountInformation(ID, UNKNOWN_ID, regionMain, endpoint):
    """
    Fetch account information from the specified endpoint with caching.
    
    Args:
        ID (str): User ID.
        UNKNOWN_ID (str): Secondary ID (set to "7" in this case).
        regionMain (str): Region code.
        endpoint (str): API endpoint (e.g., "/GetPlayerPersonalShow").
    
    Returns:
        dict: Parsed response data or an error dictionary.
    """
    regionMain = regionMain.upper()
    if regionMain not in SUPPORTED_REGIONS:
        return {"error": "Unsupported region", "message": f"Supported regions: {', '.join(SUPPORTED_REGIONS)}"}
    
    # Try to get player data from cache first
    cached_data = get_player_data_from_cache(ID, regionMain)
    if cached_data:
        try:
            player_data = json.loads(cached_data)
            print(f"Using cached player data for {ID} in {regionMain}")
            return player_data
        except:
            pass
    
    # If not in cache, fetch from API
    print(f"Fetching new player data for {ID} in {regionMain}")
    json_data = json.dumps({"a": ID, "b": UNKNOWN_ID})
    encoded_result = await json_to_proto(json_data, main_pb2.GetPlayerPersonalShow())
    payload = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, encoded_result)
    
    token, region, serverUrl = await create_jwt(regionMain)
    if not token:
        return {"error": "Authentication failed", "message": "Could not generate JWT"}
    
    headers = {
        'User-Agent': USERAGENT,
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream",
        'Authorization': token,
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': RELEASEVERSION
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(serverUrl + endpoint, data=payload, headers=headers)
        response_content = response.content
        message_type = AccountPersonalShow_pb2.AccountPersonalShowInfo  # Correct type for GetPlayerPersonalShow
        try:
            message = json.loads(json_format.MessageToJson(decode_protobuf(response_content, message_type)))
            
            # Cache the player data
            set_player_data_to_cache(ID, regionMain, message)
            print(f"Cached player data for {ID} in {regionMain}")
            
            return message
        except Exception as e:
            return {"error": "Failed to parse response", "details": str(e)}
