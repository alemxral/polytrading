import asyncio
import websockets
import json
import logging
from dotenv import load_dotenv
from wsocket.wsocket_handlers import (
    BookMessageHandler,
    PriceChangeMessageHandler,
    TickSizeChangeMessageHandler,
    LastTradePriceMessageHandler,
    TradeMessageHandler, 
    OrderMessageHandler,
)


load_dotenv()

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
        # In-memory store for each asset's order book data.
        self.token_data = {}
        # Instantiate message handlers.
        self.book_handler = BookMessageHandler(save_to_file=True)
        self.price_change_handler = PriceChangeMessageHandler(save_to_file=True)
        self.tick_size_handler = TickSizeChangeMessageHandler(save_to_file=True)
        self.last_trade_handler = LastTradePriceMessageHandler(save_to_file=True)

    def build_subscription_message(self):
        return {"assets_ids": self.assets_ids, "type": "market"}

    async def handle_message(self, message):
        # If the message is a list, iterate through each one.
        if isinstance(message, list):
            for m in message:
                await self.handle_message(m)
            return

        event_type = message.get("event_type")
        if event_type == "book":
            # Process a full book update.
            book_msg = self.book_handler.process(message)
            asset_id = message.get("asset_id")
            if asset_id:
                self.token_data[asset_id] = book_msg
            logger.info(f"[BOOK] Processed for asset {asset_id}: {book_msg}")
        elif event_type == "price_change":
            asset_id = message.get("asset_id")
            if asset_id in self.token_data and hasattr(self.token_data[asset_id], "update_price_change"):
                self.token_data[asset_id].update_price_change(message)
                logger.info(f"[PRICE_CHANGE] Updated book for asset {asset_id}.")
            else:
                # Fallback: create a new book message and update.
                book_msg = self.book_handler.process(message)
                if asset_id:
                    self.token_data[asset_id] = book_msg
                logger.info(f"[PRICE_CHANGE] Created new book for asset {asset_id} from price_change message.")
        elif event_type == "tick_size_change":
            asset_id = message.get("asset_id")
            if asset_id in self.token_data and hasattr(self.token_data[asset_id], "update_tick_size_change"):
                self.token_data[asset_id].update_tick_size_change(message)
                logger.info(f"[TICK_SIZE_CHANGE] Updated tick size for asset {asset_id}.")
            else:
                book_msg = self.book_handler.process(message)
                book_msg.update_tick_size_change(message)
                if asset_id:
                    self.token_data[asset_id] = book_msg
                logger.info(f"[TICK_SIZE_CHANGE] Created new book for asset {asset_id} from tick_size_change message.")
        elif event_type == "last_trade_price":
            asset_id = message.get("asset_id")
            if asset_id in self.token_data and hasattr(self.token_data[asset_id], "update_last_trade_price"):
                self.token_data[asset_id].update_last_trade_price(message)
            else:
                book_msg = self.book_handler.process(message)
                book_msg.update_last_trade_price(message)
                if asset_id:
                    self.token_data[asset_id] = book_msg
            logger.info(f"[LAST_TRADE_PRICE] Processed for asset {asset_id}.")
        else:
            logger.info(f"[MARKET] Unhandled event type: {event_type}")


# --- User WebSocket Client ---
class UserWSSClient(BaseWSSClient):
    def __init__(self, markets, auth=None, ws_url=WS_USER_URL):
        super().__init__(ws_url, channel_type="user")
        self.markets = markets
        # Load authentication from environment variables if not provided.
        if auth is None:
            auth = {
                "api_key": os.getenv("API_KEY"),
                "api_secret": os.getenv("API_SECRET"),
                "api_passphrase": os.getenv("API_PASSPHRASE")
            }
        self.auth = auth
        self.order_book_data = {}
        self.trade_handler = TradeMessageHandler(save_to_file=True)
        self.order_handler = OrderMessageHandler(save_to_file=True)

    def build_subscription_message(self):
        return {"auth": self.auth, "markets": self.markets, "type": "user"}

    async def handle_message(self, message):
        # If message is a list, process each message individually.
        if isinstance(message, list):
            for m in message:
                await self.handle_message(m)
            return

        event_type = message.get("event_type")
        if event_type == "trade":
            trade_msg = self.trade_handler.process(message)
            logger.info(f"[TRADE] Processed trade message: {trade_msg}")
            # Example: you can query maker order fields:
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

# -------------------- Example Usage --------------------
if __name__ == "__main__":
    # To run the market client:
    market_assets = [
        "65818619657568813474341868652308942079804919287380422192892211131408793125422"
    ]
    market_client = MarketWSSClient(assets_ids=market_assets, ws_url=WS_MARKET_URL)
    
    # Uncomment to run market client:
    asyncio.run(market_client.run())
    
    # To run the user client, comment out the market client run above and use:
    # user_markets = [
    #     "0xbd31dc8a20211944f6b70f31557f1001557b59905b7738480ca09bd4532f84af"
    # ]
    # auth = {"api_key": "your_api_key", "secret": "your_secret", "api_passphrase": "your_passphrase"}
    # user_client = UserWSSClient(markets=user_markets, auth=auth, ws_url=WS_USER_URL)
    # asyncio.run(user_client.run())
