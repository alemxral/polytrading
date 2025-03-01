import asyncio
import websockets
import json
import logging
import os
from dotenv import load_dotenv
from collections import defaultdict

# --- Configuration & Logging ---
load_dotenv()  # Load environment variables from .env if available
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Wsockt")

# Default WebSocket endpoint for market data
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# File containing JSON token objects to track (for market channel)
TOKENS_FILE = "tokens_premier_league.json"

def load_market_token_ids(filepath=TOKENS_FILE, filters=None):
    """
    Loads token IDs from a JSON file, with an optional filter to select tokens by fields.
    
    The JSON file is expected to contain an array of token objects, each with at least:
      - "token_id": string representing the token ID.
    
    :param filepath: Path to the JSON file.
    :param filters: Optional dictionary of field-value pairs. For example, {"outcome": "Yes"}
                    will only include tokens where token["outcome"] equals "Yes".
                    
    Returns:
        List of token IDs that match the filter criteria (if provided).
    """
    if not os.path.exists(filepath):
        logger.error(f"Token file '{filepath}' not found.")
        return []
    try:
        with open(filepath, "r") as f:
            tokens = json.load(f)
        
        # Apply filters if provided.
        if filters:
            filtered_tokens = []
            for token in tokens:
                match = True
                for key, expected in filters.items():
                    if token.get(key) != expected:
                        match = False
                        break
                if match:
                    filtered_tokens.append(token)
            tokens = filtered_tokens
            logger.debug(f"Filtered tokens: {len(tokens)} tokens match filters {filters}.")
        
        token_ids = [token.get("token_id") for token in tokens if token.get("token_id")]
        logger.info(f"Loaded {len(token_ids)} token IDs from '{filepath}'.")
        return token_ids
    except Exception as e:
        logger.error(f"Error loading tokens from {filepath}: {e}")
        return []


# --- Base WebSocket Client Class ---
class BaseWSSClient:
    """
    BaseWSSClient provides common functionality for connecting to a Polymarket CLOP API WebSocket channel.
    
    Subclasses must implement:
      - build_subscription_message(): constructs the subscription message (dict) to be sent.
      - handle_message(message): processes an incoming message.
    """
    def __init__(self, ws_url, channel_type):
        """
        :param ws_url: The WebSocket URL endpoint.
        :param channel_type: A string, "market" or "user".
        """
        self.ws_url = ws_url
        self.channel_type = channel_type
        self.websocket = None

    async def connect(self):
        """Establish the WebSocket connection."""
        logger.info(f"[{self.channel_type.upper()}] Connecting to {self.ws_url} ...")
        try:
            self.websocket = await websockets.connect(self.ws_url)
            logger.info(f"[{self.channel_type.upper()}] Connected successfully.")
        except Exception as e:
            logger.error(f"[{self.channel_type.upper()}] Connection failed: {e}")
            raise e

    def build_subscription_message(self):
        """
        Constructs the subscription message.
        
        Must be overridden by subclasses.
        """
        raise NotImplementedError("Subclasses must implement build_subscription_message()")

    async def subscribe(self):
        """Sends the subscription message to the WebSocket."""
        sub_msg = self.build_subscription_message()
        try:
            await self.websocket.send(json.dumps(sub_msg))
            logger.info(f"[{self.channel_type.upper()}] Sent subscription message: {sub_msg}")
        except Exception as e:
            logger.error(f"[{self.channel_type.upper()}] Failed to send subscription message: {e}")

    async def listen(self):
        """Continuously listens for incoming messages and processes them."""
        while True:
            try:
                msg = await self.websocket.recv()
                data = json.loads(msg)
                logger.info(f"[{self.channel_type.upper()}] Received message: {data}")
                await self.handle_message(data)
            except Exception as e:
                logger.error(f"[{self.channel_type.upper()}] Error receiving message: {e}")
                break

    async def handle_message(self, message):
        """
        Processes an incoming message.
        
        Must be overridden by subclasses.
        """
        raise NotImplementedError("Subclasses must implement handle_message()")

    async def run(self):
        """Connects, subscribes, and listens to the WebSocket channel."""
        await self.connect()
        await self.subscribe()
        await self.listen()


class MarketWSSClient(BaseWSSClient):
    """
    MarketWSSClient handles the public market channel.
    
    Subscription Message:
      {
          "assets_ids": [ <list of token IDs> ],
          "type": "market"
      }
    
    Expected Response Types (examples):
      - Book Message:
          {
              "event_type": "book",
              "asset_id": "<token_id>",
              "market": "<condition_id>",
              "timestamp": "<unix_timestamp_ms>",
              "hash": "<hash>",
              "bids": [ { "price": "<price>", "size": "<size>" }, ... ],
              "asks": [ { "price": "<price>", "size": "<size>" }, ... ]
          }
      - Price Change Message, Tick Size Change Message, etc.
    
    Investment Strategy:
      When a book message is received, sum the prices of the top three bid levels.
      If the sum is less than 100, calculate the difference and simulate a buy order for that amount.
    
    Internal Data Storage:
      For each token (asset_id), data is stored as:
      
      {
          "market": "<condition_id>",
          "timestamp": "<latest_timestamp>",
          "best_buys": [ "<best bid price>" ],
          "best_buys_size": [ "<best bid size>" ],
          "second_best_buys": [ "<second-best bid price>" ],
          "second_best_buys_size": [ "<second-best bid size>" ],
          "best_sells": [ "<best ask price>" ],
          "best_sells_size": [ "<best ask size>" ],
          "second_best_sells": [ "<second-best ask price>" ],
          "second_best_sells_size": [ "<second-best ask size>" ],
          "logs": { "<event_type>": "<timestamp>", ... }
      }
    """
    def __init__(self, assets_ids, ws_url=WS_URL):
        """
        :param assets_ids: List of token IDs to subscribe for.
        """
        super().__init__(ws_url, channel_type="market")
        self.assets_ids = assets_ids
        # Initialize internal storage with default structure.
        self.token_data = {}  # Key: token_id, Value: dict as specified.

    def build_subscription_message(self):
        return {
            "assets_ids": self.assets_ids,
            "type": "market"
        }

    def extract_best_levels(self, levels):
        """
        Given a list of order levels (each a dict with "price" and "size"),
        returns a tuple:
            (best_price, best_size, second_best_price, second_best_size)
        If levels is empty, returns empty strings.
        """
        if not levels or not isinstance(levels, list):
            return "", "", "", ""
        best = levels[0]
        best_price = best.get("price", "")
        best_size = best.get("size", "")
        if len(levels) >= 2:
            second = levels[1]
            second_best_price = second.get("price", "")
            second_best_size = second.get("size", "")
        else:
            second_best_price, second_best_size = "", ""
        return best_price, best_size, second_best_price, second_best_size

    async def handle_message(self, message):
        # If the message is a list, process each element.
        if isinstance(message, list):
            for m in message:
                await self.handle_message(m)
            return

        event_type = message.get("event_type")
        asset_id = message.get("asset_id")
        timestamp = message.get("timestamp", "")
        if asset_id is None:
            logger.info("[MARKET] Received message without asset_id.")
            return

        # Ensure structure for this asset_id exists
        if asset_id not in self.token_data:
            self.token_data[asset_id] = {
                "market": message.get("market", ""),
                "timestamp": timestamp,
                "best_buys": [""],
                "best_buys_size": [""],
                "second_best_buys": [""],
                "second_best_buys_size": [""],
                "best_sells": [""],
                "best_sells_size": [""],
                "second_best_sells": [""],
                "second_best_sells_size": [""],
                "logs": {}
            }
        # Update logs with current event.
        self.token_data[asset_id]["logs"][event_type] = timestamp

        if event_type == "book":
            market = message.get("market", self.token_data[asset_id].get("market", ""))
            # Use correct keys: "bids" and "asks"
            bids = message.get("bids", [])
            asks = message.get("asks", [])
            best_bid, best_bid_size, second_best_bid, second_best_bid_size = self.extract_best_levels(bids)
            best_sell, best_sell_size, second_best_sell, second_best_sell_size = self.extract_best_levels(asks)
            # Update internal structure exactly as specified.
            self.token_data[asset_id].update({
                "market": market,
                "timestamp": timestamp,
                "best_buys": [best_bid],
                "best_buys_size": [best_bid_size],
                "second_best_buys": [second_best_bid],
                "second_best_buys_size": [second_best_bid_size],
                "best_sells": [best_sell],
                "best_sells_size": [best_sell_size],
                "second_best_sells": [second_best_sell],
                "second_best_sells_size": [second_best_sell_size]
            })
            logger.info(f"[MARKET BOOK] Updated data for asset {asset_id}: {self.token_data[asset_id]}")
            # Execute the investment strategy.
            await self.execute_investment_strategy(message)
        elif event_type == "price_change":
            # For price_change, evaluate each change to see if it improves the stored best prices.
            changes = message.get("changes", [])
            # For each change, if side is SELL, update best sells if the new price is lower.
            # If side is BUY, update best buys if the new price is higher.
            # We'll update only the best level here for simplicity.
            for change in changes:
                change_price = change.get("price", "")
                change_size = change.get("size", "")
                side = change.get("side", "").upper()
                try:
                    change_price = float(change_price)
                except Exception:
                    continue
                if side == "SELL":
                    current_best_sell = self.token_data[asset_id].get("best_sells", [""])[0]
                    try:
                        current_best_sell_val = float(current_best_sell) if current_best_sell != "" else None
                    except Exception:
                        current_best_sell_val = None
                    if current_best_sell_val is None or change_price < current_best_sell_val:
                        # Shift current best sell to second best, then update best sell.
                        self.token_data[asset_id]["second_best_sells"] = self.token_data[asset_id]["best_sells"]
                        self.token_data[asset_id]["second_best_sells_size"] = self.token_data[asset_id]["best_sells_size"]
                        self.token_data[asset_id]["best_sells"] = [str(change_price)]
                        self.token_data[asset_id]["best_sells_size"] = [change_size]
                        logger.info(f"[MARKET PRICE CHANGE] Updated best sells for asset {asset_id} to {change_price} with size {change_size}")
                elif side == "BUY":
                    current_best_bid = self.token_data[asset_id].get("best_buys", [""])[0]
                    try:
                        current_best_bid_val = float(current_best_bid) if current_best_bid != "" else None
                    except Exception:
                        current_best_bid_val = None
                    if current_best_bid_val is None or change_price > current_best_bid_val:
                        # Shift current best bid to second best, then update best bid.
                        self.token_data[asset_id]["second_best_buys"] = self.token_data[asset_id]["best_buys"]
                        self.token_data[asset_id]["second_best_buys_size"] = self.token_data[asset_id]["best_buys_size"]
                        self.token_data[asset_id]["best_buys"] = [str(change_price)]
                        self.token_data[asset_id]["best_buys_size"] = [change_size]
                        logger.info(f"[MARKET PRICE CHANGE] Updated best buys for asset {asset_id} to {change_price} with size {change_size}")
            # Update timestamp and log the event.
            self.token_data[asset_id].update({
                "timestamp": timestamp
            })
            logger.info(f"[MARKET PRICE CHANGE] Processed price change for asset {asset_id}.")
        elif event_type == "tick_size_change":
            self.token_data[asset_id].update({
                "timestamp": timestamp
            })
            logger.info(f"[MARKET TICK SIZE CHANGE] Processed tick size change for asset {asset_id}.")
        else:
            logger.info(f"[MARKET] Unhandled message type: {event_type}")

    async def execute_investment_strategy(self, message):
        """
        Sums the prices of the top three bid levels from a book message.
        If the total is less than 100, simulates a buy order for the difference.
        """
        bids = message.get("bids", [])
        try:
            total_price = sum(float(buy.get("price", 0)) for buy in bids[:3])
        except Exception as e:
            logger.error(f"Error calculating total bid price: {e}")
            return
        logger.info(f"Total price of best bids: {total_price}")
        if total_price < 100:
            difference = 100 - total_price
            token_id = message.get("asset_id")
            logger.info(f"Investment strategy triggered: Total bid price ({total_price}) < 100.")
            logger.info(f"Simulating buy order for token {token_id} for amount {difference}.")
            await self.buy_token(token_id, difference)
        else:
            logger.info("Investment strategy not triggered.")

    async def buy_token(self, token_id, amount):
        """
        Dummy function to simulate a buy order.
        In a real implementation, integrate with your trading system.
        """
        logger.info(f"Executing buy order for token {token_id} for amount {amount}.")
        await asyncio.sleep(0.1)

    async def save_token_data(self, filepath="market_data.json", interval=5):
        """
        Periodically saves the internal token_data to a JSON file.
        """
        while True:
            try:
                with open(filepath, "w") as f:
                    json.dump(self.token_data, f, indent=2)
                logger.info(f"Saved token data to {filepath}.")
            except Exception as e:
                logger.error(f"Error saving token data: {e}")
            await asyncio.sleep(interval)

    async def run(self):
        """
        Connects, subscribes, listens, and concurrently saves token data.
        """
        await self.connect()
        await self.subscribe()
        await asyncio.gather(
            self.listen(),
            self.save_token_data()
        )


class UserWSSClient(BaseWSSClient):
    """
    UserWSSClient handles the authenticated user channel.
    
    Subscription Message (for user channel):
      {
          "auth": {
              "apiKey": <your_api_key>,
              "secret": <your_api_secret>,
              "passphrase": <your_api_passphrase>
          },
          "markets": [ <list of market (condition) IDs> ],
          "type": "user"
      }
      
    Expected Response Types include:
      - Trade Message: for order matches/updates.
      - Order Message: for order placements, updates, cancellations.
      - Book Message (if received on user channel): this updated version processes book messages,
        extracting the best bid and ask prices along with their amounts, plus the second-best levels.
        
    The class maintains an internal dictionary (self.order_book_data) keyed by asset_id,
    which is updated each time a book message is received.
    """
    def __init__(self, markets, auth, ws_url=WS_URL):
        """
        :param markets: List of market (condition) IDs to subscribe for.
        :param auth: Dictionary containing "apiKey", "secret", and "passphrase".
        """
        super().__init__(ws_url, channel_type="user")
        self.markets = markets
        self.auth = auth
        # Internal storage for order book data for each token (asset_id)
        self.order_book_data = {}

    def build_subscription_message(self):
        return {
            "auth": self.auth,
            "markets": self.markets,
            "type": "user"
        }

    async def handle_message(self, message):
        # If the message is a list, iterate over each element.
        if isinstance(message, list):
            for m in message:
                await self.handle_message(m)
            return

        event_type = message.get("event_type")
        if event_type == "trade":
            logger.info(f"[USER TRADE] {message}")
        elif event_type == "order":
            logger.info(f"[USER ORDER] {message}")
        elif event_type == "book":
            # Process book message: update order book data with best & second-best levels.
            asset_id = message.get("asset_id")
            market = message.get("market")
            timestamp = message.get("timestamp")
            # In this context, assume the book message has "buys" for bids and "sells" for asks.
            bids = message.get("buys", [])
            sells = message.get("sells", [])
            # Determine best bid and second-best bid.
            best_bid = bids[0] if len(bids) >= 1 else {}
            second_best_bid = bids[1] if len(bids) >= 2 else {}
            best_bid_amount = best_bid.get("size", "")
            second_best_bid_amount = second_best_bid.get("size", "")
            # Determine best sell and second-best sell.
            best_sell = sells[0] if len(sells) >= 1 else {}
            second_best_sell = sells[1] if len(sells) >= 2 else {}
            best_sell_amount = best_sell.get("size", "")
            second_best_sell_amount = second_best_sell.get("size", "")
            # Update the internal order book data.
            self.order_book_data[asset_id] = {
                "market": market,
                "timestamp": timestamp,
                "best_bid": best_bid.get("price", ""),
                "best_bid_amount": best_bid_amount,
                "second_best_bid": second_best_bid.get("price", ""),
                "second_best_bid_amount": second_best_bid_amount,
                "best_sell": best_sell.get("price", ""),
                "best_sell_amount": best_sell_amount,
                "second_best_sell": second_best_sell.get("price", ""),
                "second_best_sell_amount": second_best_sell_amount,
                "full_message": message
            }
            logger.info(f"[USER BOOK] Updated order book for asset {asset_id}: {self.order_book_data[asset_id]}")
        else:
            logger.info(f"[USER] Unhandled message type: {event_type}")


# --- Top-Level Wsockt Manager ---
# --- Top-Level Manager (Market Only) ---
class Wsockt:
    """
    Wsockt is the top-level class to manage WebSocket connections.
    
    Currently, it is configured to connect only to the market channel.
    In the future, you can extend this manager to also connect to the user channel.
    """
    def __init__(self, tokens_filepath=TOKENS_FILE, token_filters=None):
        """
        :param tokens_filepath: Path to the JSON file with tokens for the market channel.
        :param token_filters: Optional dict to filter token objects (e.g., {"outcome": "Yes"}).
        """
        logger.debug("Initializing Wsockt manager.")
        self.market_token_ids = load_market_token_ids(tokens_filepath, filters=token_filters)
        logger.debug(f"Market token IDs loaded: {self.market_token_ids}")
        self.market_client = MarketWSSClient(assets_ids=self.market_token_ids)
        logger.debug("MarketWSSClient initialized.")
        logger.info("Wsockt manager initialized successfully (market channel only).")

    async def run(self):
        logger.debug("Starting market channel client.")
        await self.market_client.run()
        logger.debug("Market channel client completed.")
        # Future extension: run both market and user channels concurrently.
        # await asyncio.gather(
        #     self.market_client.run(),
        #     self.user_client.run()
        # )


# --- Example Usage ---
if __name__ == "__main__":
    # Optionally, filter tokens (e.g., only tokens where outcome == "Yes")
    token_filters = {"outcome": "Yes"}
    market_token_ids = load_market_token_ids(filepath=TOKENS_FILE, filters=token_filters)
    
    # Instantiate the Market WebSocket client with the loaded token IDs.
    market_client = MarketWSSClient(assets_ids=market_token_ids)
    
    try:
        asyncio.run(market_client.run())
    except KeyboardInterrupt:
        logger.info("Market WebSocket client stopped by user.")

# --- Future Extension ---
# To connect to both the market and user channels, you can use the top-level Wsockt manager:
# from your_module import Wsockt
# user_markets = ["<market_id_1>", "<market_id_2>", ...]
# auth_info = {
#     "apiKey": os.getenv("API_KEY", "your_api_key"),
#     "secret": os.getenv("API_SECRET", "your_api_secret"),
#     "passphrase": os.getenv("API_PASSPHRASE", "your_api_passphrase")
# }
# ws_manager = Wsockt(user_markets=user_markets, auth=auth_info, token_filters=token_filters)
# asyncio.run(ws_manager.run())