import asyncio
import websockets
import json
import logging
import os
from datetime import datetime
from wsocket_handlers import (
    BookMessageHandler,
    PriceChangeMessageHandler,
    TickSizeChangeMessageHandler,
    LastTradePriceMessageHandler,
    TradeMessageHandler,
    OrderMessageHandler
)


# --- Configuration & Logging ---
logger = logging.getLogger("Wsockt")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# Endpoints for Market and User channels
WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
WS_USER_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"

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
                logger.debug(f"[{self.channel_type.upper()}] Message received.")
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


# --- Market WebSocket Client ---
class MarketWSSClient(BaseWSSClient):
    def __init__(self, assets_ids, ws_url=WS_MARKET_URL):
        super().__init__(ws_url, channel_type="market")
        self.assets_ids = assets_ids
        # In-memory store for each asset's orderbook data.
        self.token_data = {}

        # Instantiate message handlers.
        self.book_handler = BookMessageHandler(save_to_file=True)
        self.price_change_handler = PriceChangeMessageHandler(save_to_file=True)
        self.tick_size_handler = TickSizeChangeMessageHandler(save_to_file=True)
        self.last_trade_handler = LastTradePriceMessageHandler(save_to_file=True)

    def build_subscription_message(self):
        return {"assets_ids": self.assets_ids, "type": "market"}

    async def handle_message(self, message):
        event_type = message.get("event_type")
        if event_type == "book":
            # Process a full book update.
            result = self.book_handler.process(message)
            logger.info(f"[BOOK] Processed: {result}")
            asset_id = message.get("asset_id")
            if asset_id:
                self.token_data[asset_id] = message  # Refresh token data.
        elif event_type == "price_change":
            result = self.price_change_handler.process(message)
            logger.info(f"[PRICE_CHANGE] Processed: {result}")
        elif event_type == "tick_size_change":
            result = self.tick_size_handler.process(message)
            logger.info(f"[TICK_SIZE_CHANGE] Processed: {result}")
        elif event_type == "last_trade_price":
            result = self.last_trade_handler.process(message)
            logger.info(f"[LAST_TRADE_PRICE] Processed: {result}")
        else:
            logger.info(f"[MARKET] Unhandled event type: {event_type}")


# --- User WebSocket Client ---
class UserWSSClient(BaseWSSClient):
    def __init__(self, markets, auth, ws_url=WS_USER_URL):
        super().__init__(ws_url, channel_type="user")
        self.markets = markets
        self.auth = auth
        # Dictionary to store user-related data (e.g. order book, trades)
        self.order_book_data = {}

        # Instantiate handlers.
        self.trade_handler = TradeMessageHandler(save_to_file=True)
        self.order_handler = OrderMessageHandler(save_to_file=True)

    def build_subscription_message(self):
        return {"auth": self.auth, "markets": self.markets, "type": "user"}

    async def handle_message(self, message):
        event_type = message.get("event_type")
        if event_type == "trade":
            trade_msg = self.trade_handler.process(message)
            logger.info(f"[TRADE] Processed trade message: {trade_msg}")
            # Example: query maker order details if needed.
            # maker_info = trade_msg.get_maker_order_fields(order_id, ["price", "owner"])
        elif event_type == "order":
            order_msg = self.order_handler.process(message)
            logger.info(f"[ORDER] Processed order message: {order_msg}")
        elif event_type == "book":
            asset_id = message.get("asset_id")
            self.order_book_data[asset_id] = message
            logger.info(f"[USER BOOK] Updated order book for asset {asset_id}.")
        else:
            logger.info(f"[USER] Unhandled event type: {event_type}")


# --- Example Usage ---
if __name__ == "__main__":
    # Example for Market channel
    market_assets = [
        "65818619657568813474341868652308942079804919287380422192892211131408793125422"
    ]
    market_client = MarketWSSClient(assets_ids=market_assets, ws_url=WS_MARKET_URL)
    
    # To run the market client:
    # asyncio.run(market_client.run())

    # Example for User channel
    user_markets = [
        "0xbd31dc8a20211944f6b70f31557f1001557b59905b7738480ca09bd4532f84af"
    ]
    auth = {"apiKey": "your_api_key", "secret": "your_secret", "passphrase": "your_passphrase"}
    user_client = UserWSSClient(markets=user_markets, auth=auth, ws_url=WS_USER_URL)
    
    # To run the user client (comment out one if testing individually)
    # asyncio.run(user_client.run())
    
    # For demonstration, you could run one at a time:
    asyncio.run(market_client.run())
    # asyncio.run(user_client.run())
