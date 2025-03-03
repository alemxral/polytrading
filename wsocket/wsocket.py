import asyncio
import websockets
import json
import logging
from datetime import datetime
from wsocket_handlers import (
    BookMessageHandler,
    PriceChangeMessageHandler,
    TickSizeChangeMessageHandler,
    LastTradePriceMessageHandler,
)

logger = logging.getLogger("Wsockt")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

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
    def __init__(self, assets_ids, ws_url=WS_URL):
        super().__init__(ws_url, channel_type="market")
        self.assets_ids = assets_ids
        self.token_data = {}

        # Instantiate handlers.
        self.book_handler = BookMessageHandler(save_to_file=True)
        self.price_change_handler = PriceChangeMessageHandler(save_to_file=True)
        self.tick_size_handler = TickSizeChangeMessageHandler(save_to_file=True)
        self.last_trade_handler = LastTradePriceMessageHandler(save_to_file=True)

    def build_subscription_message(self):
        return {"assets_ids": self.assets_ids, "type": "market"}

    async def handle_message(self, message):
        event_type = message.get("event_type")
        if event_type == "book":
            result = self.book_handler.process(message)
            logger.info(f"[BOOK] Processed: {result}")
            asset_id = message.get("asset_id")
            if asset_id:
                self.token_data[asset_id] = message  # Full refresh of token data.
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

if __name__ == "__main__":
    # Example usage: provide asset IDs as needed.
    assets = ["65818619657568813474341868652308942079804919287380422192892211131408793125422"]
    client = MarketWSSClient(assets_ids=assets, ws_url=WS_URL)
    asyncio.run(client.run())
