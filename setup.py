import os
import json
import logging
import asyncio
from dotenv import load_dotenv
import yaml
from py_clob_client.client import ClobClient
import websockets  # async websockets

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("polytrading-ws")

# Load environment variables from .env file
load_dotenv()

# Load endpoints from YAML config
with open("config/settings.yaml", "r") as f:
    config = yaml.safe_load(f)
endpoints = config.get("endpoints", {})

HOST = endpoints.get("rest", os.getenv("CLOB_HOST", "https://clob.polymarket.com"))
WS_MARKET_URL = endpoints.get("websocket_market", "wss://ws-subscriptions-clob.polymarket.com/ws/market")
WS_USER_URL = endpoints.get("websocket_user", "wss://ws-subscriptions-clob.polymarket.com/ws/user")
CHAIN_ID = int(os.getenv("CHAIN_ID", 137))
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER = os.getenv("FUNDER")
signature_type = config.get("signature_type", 0)

print(f"[DEBUG] HOST: {HOST}")
print(f"[DEBUG] WS_MARKET_URL: {WS_MARKET_URL}")
print(f"[DEBUG] WS_USER_URL: {WS_USER_URL}")
print(f"[DEBUG] CHAIN_ID: {CHAIN_ID}")
print(f"[DEBUG] PRIVATE_KEY is set: {bool(PRIVATE_KEY) and PRIVATE_KEY != ''}")
print(f"[DEBUG] FUNDER is set: {bool(FUNDER) and FUNDER != ''}")
print(f"[DEBUG] signature_type: {signature_type}")

# Authenticate with REST API
client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=CHAIN_ID,
    signature_type=signature_type,
    funder=FUNDER
)
try:
    client.set_api_creds(client.create_or_derive_api_creds())
    api_keys = client.get_api_keys()
    print(f"[DEBUG] API authentication successful. API Keys: {api_keys}")
except Exception as e:
    print(f"[ERROR] API authentication failed: {e}")

# --- Base WebSocket Client ---
class BaseWSSClient:
    def __init__(self, ws_url, channel_type):
        self.ws_url = ws_url
        self.channel_type = channel_type
        self.websocket = None

    async def connect(self):
        logger.info(f"[{self.channel_type.upper()}] Connecting to {self.ws_url} ...")
        try:
            self.websocket = await websockets.connect(self.ws_url)
            logger.info(f"[{self.channel_type.upper()}] Connected successfully.")
        except Exception as e:
            logger.error(f"[{self.channel_type.upper()}] Connection failed: {e}")
            raise e

    def build_subscription_message(self):
        raise NotImplementedError("Subclasses must implement build_subscription_message()")

    async def subscribe(self):
        sub_msg = self.build_subscription_message()
        try:
            await self.websocket.send(json.dumps(sub_msg))
            logger.info(f"[{self.channel_type.upper()}] Subscription message sent.")
        except Exception as e:
            logger.error(f"[{self.channel_type.upper()}] Failed to send subscription message: {e}")

    async def listen(self):
        while True:
            try:
                msg = await self.websocket.recv()
                data = json.loads(msg)
                logger.debug(f"[{self.channel_type.upper()}] Message received: {data}")
                await self.handle_message(data)
            except Exception as e:
                logger.error(f"[{self.channel_type.upper()}] Error receiving message: {e}")
                break

    async def handle_message(self, message):
        raise NotImplementedError("Subclasses must implement handle_message()")

    async def run(self):
        await self.connect()
        await self.subscribe()
        await self.listen()

# Example subclass for Market channel
class MarketWSSClient(BaseWSSClient):
    def __init__(self, ws_url, asset_ids):
        super().__init__(ws_url, "market")
        self.asset_ids = asset_ids if isinstance(asset_ids, list) else [asset_ids]

    def build_subscription_message(self):
        return {
            "type": "Market",
            "assets_ids": self.asset_ids
        }

    async def handle_message(self, message):
        logger.info(f"[MARKET] Message: {message}")

class UserWSSClient(BaseWSSClient):
    def __init__(self, ws_url, markets, api_key, api_secret, api_passphrase):
        super().__init__(ws_url, "user")
        self.markets = markets if isinstance(markets, list) else [markets]
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase

    def build_subscription_message(self):
        return {
            "type": "User",
            "auth": {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "passphrase": self.api_passphrase
            },
            "markets": self.markets
        }

    async def handle_message(self, message):
        logger.info(f"[USER] Message: {message}")

# To run the market websocket client
if __name__ == "__main__":
    # Example asset_id and market_id (replace with real ones as needed)
    asset_ids = ["0x02684b3ef5bcc5c544c225fc14df6d2d4a2f67795b609ea92642ca34f4d4c984"]
    market_ids = ["0xa2dc460008f3e61d55462ec2b05d9ec8d2e52c8f9981225b55642cc8e943f16a"]

    # Get API credentials from the authenticated REST client
    try:
        api_creds = client.create_or_derive_api_creds()
        api_key = api_creds.api_key
        api_secret = api_creds.api_secret
        api_passphrase = api_creds.api_passphrase
        print(f"[DEBUG] API Key: {api_key}\n[DEBUG] API Secret: {api_secret}\n[DEBUG] API Passphrase: {api_passphrase}")
    except Exception as e:
        logger.error(f"[USER] Could not get API credentials: {e}")
        api_key = api_secret = api_passphrase = None

    # Run both clients concurrently
    async def run_clients():
        # market_client = MarketWSSClient(WS_MARKET_URL, asset_ids)
        user_client = UserWSSClient(WS_USER_URL, market_ids, api_key, api_secret, api_passphrase)
        await asyncio.gather(
            # market_client.run(),
            user_client.run()
        )

    asyncio.run(run_clients())