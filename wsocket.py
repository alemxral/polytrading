import asyncio
import websockets
import json
import logging
import os
from dotenv import load_dotenv
from collections import defaultdict
import uuid
from datetime import datetime

# --- Configuration & Logging ---
load_dotenv()  # Load environment variables from .env if available
# Create and configure the logger.
logger = logging.getLogger("Wsockt")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

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
        """Continuously listens for incoming messages, logs them globally, and processes them."""
        global_log_file = "global_message_log.json"
        while True:
            try:
                msg = await self.websocket.recv()
                data = json.loads(msg)
                
                # Append the received message to the global JSON log.
                try:
                    if os.path.exists(global_log_file):
                        with open(global_log_file, "r") as f:
                            global_log = json.load(f)
                            if not isinstance(global_log, list):
                                global_log = []
                    else:
                        global_log = []
                except Exception as e:
                    logger.error(f"Error reading global log: {e}")
                    global_log = []
                
                global_log.append(data)
                try:
                    with open(global_log_file, "w") as f:
                        json.dump(global_log, f, indent=4)
                except Exception as e:
                    logger.error(f"Error writing global log: {e}")
                
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
 
# --- OrderSender Class ---
class OrderSender:
    """
    Dummy OrderSender for sending orders.
    In a real implementation, this class would send orders via HTTP requests.
    """
    @staticmethod
    async def send_order(token_id, order_size, order_price, weighted=False):
        try:
            logger.info(
                f"OrderSender: Sending order for token {token_id} at price {order_price} for size {order_size} (weighted: {weighted})."
            )
            # Simulate network latency or API processing.
            await asyncio.sleep(0.1)
            # Simulated response.
            response = {
                "status": "success",
                "token_id": token_id,
                "order_size": order_size,
                "order_price": order_price,
                "weighted": weighted
            }
            logger.info(f"OrderSender: Order for token {token_id} sent successfully. Response: {response}")
            return response
        except Exception as e:
            logger.error(f"OrderSender: Failed to send order for token {token_id}: {e}")
            return {"status": "error", "token_id": token_id, "error": str(e)}



class MarketWSSClient(BaseWSSClient):
    """
    MarketWSSClient handles the public market channel.

    Subscription Message:
      {
          "assets_ids": [ <list of token IDs> ],
          "type": "market"
      }

    Investment Strategy (New):
      For each token, the strategy does the following:
        1. Extract the best ask price/size and, if available, the second-best ask.
        2. Compute a candidate order for each token using:
             - Candidate size: best_ask_size (or combined with second-best ask size if available)
             - Weighted price: if second-best ask is available, a weighted average price is calculated.
        3. Sum the prices (using the best ask prices or the weighted prices).
        4. If the total is less than 100, determine an optimal uniform order size,
           which is the minimum candidate size among tokens.
        5. Log the order details to a JSON file and simulate sending orders via OrderSender.
      
    Internal Data Storage:
      For each token (asset_id), data is stored as:
      {
          "market": "<condition_id>",
          "timestamp": "<latest timestamp>",
          "best_buys": [ "<best bid price>" ],
          "best_buys_size": [ "<best bid size>" ],
          "second_best_buys": [ "<second-best bid price>" ],
          "second_best_buys_size": [ "<second-best bid size>" ],
          "best_sells": [ "<best ask price>" ],
          "best_sells_size": [ "<best ask size>" ],
          "second_best_sells": [ "<second-best ask price>" ],
          "second_best_sells_size": [ "<second-best ask size>" ],
          "logs": { ... },
          "old_tick_size": "0.01",
          "new_tick_size": "0.01"
      }
    """
    def __init__(self, assets_ids, ws_url=WS_URL):
        """
        :param assets_ids: List of token IDs to subscribe for.
        """
        super().__init__(ws_url, channel_type="market")
        self.assets_ids = assets_ids
        self.token_data = {}  # Internal storage for each token's data

    def build_subscription_message(self):
        return {
            "assets_ids": self.assets_ids,
            "type": "market"
        }

    def extract_best_level(self, levels, is_ask=True):
        """
        Given a list of order levels (each with "price" and "size"),
        returns a tuple: (best_price, best_size).
        For asks (is_ask=True), the best level is the one with the lowest price;
        for bids (is_ask=False), the best level is the one with the highest price.
        If levels is empty or invalid, returns empty strings.
        """
        if not levels or not isinstance(levels, list):
            return "", ""
        best_level = None
        for level in levels:
            try:
                price = float(level.get("price", 0))
                size = float(level.get("size", 0))
            except Exception:
                continue

            if best_level is None:
                best_level = level
            else:
                try:
                    best_price = float(best_level.get("price", 0))
                    best_size = float(best_level.get("size", 0))
                except Exception:
                    best_price, best_size = 0, 0

                if is_ask:
                    # For asks, lower price is better. If equal, higher size is preferred.
                    if price < best_price or (price == best_price and size > best_size):
                        best_level = level
                else:
                    # For bids, higher price is better. If equal, higher size is preferred.
                    if price > best_price or (price == best_price and size > best_size):
                        best_level = level
        if best_level is None:
            return "", ""
        return best_level.get("price", ""), best_level.get("size", "")

    async def handle_message(self, message):
        # Process each message in a list, if applicable.
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

        # Initialize internal structure for this asset if not present.
        if asset_id not in self.token_data:
            self.token_data[asset_id] = {
                "market": message.get("market", ""),
                "timestamp": timestamp,
                "best_buys": [""],
                "best_buys_size": [""],
                "best_sells": [""],
                "best_sells_size": [""],
                "logs": {},
                "old_tick_size": "0.01",
                "new_tick_size": "0.01"
            }
        # Update logs.
        self.token_data[asset_id]["logs"][event_type] = timestamp

        if event_type == "book":
            market = message.get("market", self.token_data[asset_id].get("market", ""))
            bids = message.get("bids", [])
            asks = message.get("asks", [])
            # For bids, get the highest price; for asks, get the lowest price.
            best_bid, best_bid_size = self.extract_best_level(bids, is_ask=False)
            best_sell, best_sell_size = self.extract_best_level(asks, is_ask=True)
            self.token_data[asset_id].update({
                "market": market,
                "timestamp": timestamp,
                "best_buys": [best_bid],
                "best_buys_size": [best_bid_size],
                "best_sells": [best_sell],
                "best_sells_size": [best_sell_size]
            })
            logger.info(f"[MARKET BOOK] Updated data for asset {asset_id}: {self.token_data[asset_id]}")
            # Call the investment strategy after processing the book update.
            await self.execute_investment_strategy()
        elif event_type == "price_change":
            changes = message.get("changes", [])
            for change in changes:
                try:
                    change_price = float(change.get("price", 0))
                except Exception:
                    continue
                change_size = change.get("size", "")
                side = change.get("side", "").upper()
                if side == "SELL":
                    # Update best ask if new price is lower or if equal price but higher size.
                    current_best_sell_str = self.token_data[asset_id].get("best_sells", [""])[0]
                    try:
                        current_best_sell_val = float(current_best_sell_str) if current_best_sell_str != "" else None
                        current_best_sell_size = float(self.token_data[asset_id].get("best_sells_size", ["0"])[0])
                    except Exception:
                        current_best_sell_val, current_best_sell_size = None, 0
                    try:
                        new_size = float(change_size) if change_size != "" else 0
                    except Exception:
                        new_size = 0
                    if current_best_sell_val is None or change_price < current_best_sell_val or (change_price == current_best_sell_val and new_size > current_best_sell_size):
                        self.token_data[asset_id]["best_sells"] = [str(change_price)]
                        self.token_data[asset_id]["best_sells_size"] = [str(change_size)]
                        logger.info(f"[MARKET PRICE CHANGE] Updated best sells for asset {asset_id} to {change_price} with size {change_size}")
                elif side == "BUY":
                    # Update best bid if new price is higher or if equal price but higher size.
                    current_best_bid_str = self.token_data[asset_id].get("best_buys", [""])[0]
                    try:
                        current_best_bid_val = float(current_best_bid_str) if current_best_bid_str != "" else None
                        current_best_bid_size = float(self.token_data[asset_id].get("best_buys_size", ["0"])[0])
                    except Exception:
                        current_best_bid_val, current_best_bid_size = None, 0
                    try:
                        new_size = float(change_size) if change_size != "" else 0
                    except Exception:
                        new_size = 0
                    if current_best_bid_val is None or change_price > current_best_bid_val or (change_price == current_best_bid_val and new_size > current_best_bid_size):
                        self.token_data[asset_id]["best_buys"] = [str(change_price)]
                        self.token_data[asset_id]["best_buys_size"] = [str(change_size)]
                        logger.info(f"[MARKET PRICE CHANGE] Updated best buys for asset {asset_id} to {change_price} with size {change_size}")
            self.token_data[asset_id]["timestamp"] = timestamp
            logger.info(f"[MARKET PRICE CHANGE] Processed price change for asset {asset_id}.")
            await self.execute_investment_strategy()
        elif event_type == "tick_size_change":
            old_tick = message.get("old_tick_size", "0.01")
            new_tick = message.get("new_tick_size", "0.01")
            self.token_data[asset_id].update({
                "timestamp": timestamp,
                "old_tick_size": old_tick,
                "new_tick_size": new_tick
            })
            logger.info(f"[MARKET TICK SIZE CHANGE] Updated tick sizes for asset {asset_id}: old {old_tick}, new {new_tick}")
        else:
            logger.info(f"[MARKET] Unhandled message type: {event_type}")

    async def execute_investment_strategy(self):
        """
        For each token, calculate the best execution price and available size (combining best and, if available, second-best asks).
        If the total sum of prices is less than 100 then an arbitrage opportunity is detected.
        The optimal size is chosen as the minimum available size among tokens (to ensure the same size can be executed for all).
        Finally, the orders (token id, price, optimal size) are wrapped into a single group (with a unique order id and timestamp),
        logged to a persistent JSON file (preserving previous orders), and orders are sent.

        Additionally, detailed token data and total price are logged to an analysis JSON file.
        """
        orders = []             # List to hold order data for each token
        log_orders = []         # For logging token data for later analysis
        token_sizes = []        # List of best-sell sizes to determine the optimal size
        standalone_prices = {}  # Dictionary to keep track of each token's best sell price

        # Process each token's data.
        for token_id, data in self.token_data.items():
            try:
                best_sell_price = (
                    float(data.get("best_sells", [None])[0])
                    if data.get("best_sells") and data["best_sells"][0] != ""
                    else None
                )
                best_sell_size = (
                    float(data.get("best_sells_size", [None])[0])
                    if data.get("best_sells_size") and data["best_sells_size"][0] != ""
                    else None
                )
            except (KeyError, IndexError, ValueError) as e:
                logger.error(f"Error processing token {token_id}: {e}")
                continue

            if best_sell_price is None or best_sell_size is None:
                continue

            # Build order candidate.
            orders.append({
                "token_id": token_id,
                "price": best_sell_price,
                "size": best_sell_size,      # Original candidate size.
                "optimal_size": None         # To be determined if arbitrage opportunity is detected.
            })
            # Record data for analysis.
            log_orders.append({
                "token_id": token_id,
                "best_sell_price": best_sell_price,
                "best_sell_size": best_sell_size
            })
            standalone_prices.setdefault(token_id, []).append({"price": best_sell_price})
            token_sizes.append(best_sell_size)

        # Log detailed analysis data.
        analysis_log_file = "analysis_log.json"
        try:
            if os.path.exists(analysis_log_file):
                with open(analysis_log_file, "r") as f:
                    analysis_data = json.load(f)
                    if not isinstance(analysis_data, list):
                        analysis_data = []
            else:
                analysis_data = []
        except Exception as e:
            logger.error(f"Error reading analysis log: {e}")
            analysis_data = []

        call_timestamp = datetime.now().isoformat() + "Z"
        analysis_entry = {
            "timestamp": call_timestamp,
            "log_orders": log_orders,
            "total_price": None
        }
        analysis_data.append(analysis_entry)

        # Sum best sell prices.
        total_price = sum(
            entry["price"]
            for price_list in standalone_prices.values()
            for entry in price_list
        )
        logger.info(f"Total price across tokens: {total_price}")
        analysis_data[-1]["total_price"] = total_price

        try:
            with open(analysis_log_file, "w") as f:
                json.dump(analysis_data, f, indent=4)
            logger.info("Analysis log updated.")
        except Exception as e:
            logger.error(f"Error saving analysis log: {e}")

        # Check if arbitrage opportunity is detected.
        if total_price < 100 and orders:
            logger.info("Arbitrage opportunity detected. Calculating optimal size...")
            optimal_size = min(token_sizes) if token_sizes else 0

            # Update each order with the computed optimal size.
            for order in orders:
                order["optimal_size"] = optimal_size

            # Generate unique order id and timestamp.
            order_id = str(uuid.uuid4())
            order_timestamp = datetime.utcnow().isoformat() + "Z"
            wrapped_order = {
                "order_id": order_id,
                "timestamp": order_timestamp,
                "total_price": total_price,
                "orders": orders
            }

            # Persist order log.
            log_file = "order_log.json"
            try:
                if os.path.exists(log_file):
                    with open(log_file, "r") as f:
                        existing_orders = json.load(f)
                        if not isinstance(existing_orders, list):
                            existing_orders = []
                else:
                    existing_orders = []
            except Exception as e:
                logger.error(f"Error reading order log: {e}")
                existing_orders = []

            existing_orders.append(wrapped_order)
            try:
                with open(log_file, "w") as f:
                    json.dump(existing_orders, f, indent=4)
                logger.info(f"Order log updated. New order id: {order_id} with optimal size: {optimal_size} and total_price: {total_price}")
            except Exception as e:
                logger.error(f"Error saving order log: {e}")

            # Simulate sending orders asynchronously using OrderSender.
            send_tasks = []
            for order in orders:
                token_id = order["token_id"]
                order_size = order["optimal_size"]
                order_price = order["price"]
                # Mark as weighted if the candidate size differs from the optimal size.
                weighted = order["size"] != order["optimal_size"]
                send_tasks.append(OrderSender.send_order(token_id, order_size, order_price, weighted))
            responses = await asyncio.gather(*send_tasks)
            logger.info(f"Order sending responses: {responses}")
        else:
            logger.info("No arbitrage opportunity detected based on current prices.")

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

# --- UserWSSClient Class ---
class UserWSSClient(BaseWSSClient):
    """
    UserWSSClient handles the authenticated user channel.
    """
    def __init__(self, markets, auth, ws_url=WS_URL):
        """
        :param markets: List of market (condition) IDs to subscribe for.
        :param auth: Dictionary containing "apiKey", "secret", and "passphrase".
        """
        super().__init__(ws_url, channel_type="user")
        self.markets = markets
        self.auth = auth
        self.order_book_data = {}

    def build_subscription_message(self):
        return {
            "auth": self.auth,
            "markets": self.markets,
            "type": "user"
        }

    async def handle_message(self, message):
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
            asset_id = message.get("asset_id")
            market = message.get("market")
            timestamp = message.get("timestamp")
            bids = message.get("buys", [])
            sells = message.get("sells", [])
            best_bid = bids[0] if len(bids) >= 1 else {}
            second_best_bid = bids[1] if len(bids) >= 2 else {}
            best_bid_amount = best_bid.get("size", "")
            second_best_bid_amount = second_best_bid.get("size", "")
            best_sell = sells[0] if len(sells) >= 1 else {}
            second_best_sell = sells[1] if len(sells) >= 2 else {}
            best_sell_amount = best_sell.get("size", "")
            second_best_sell_amount = second_best_sell.get("size", "")
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




# --- Top-Level Wsockt Manager (Market Only) ---
class Wsockt:
    """
    Wsockt is the top-level class to manage WebSocket connections.
    
    Currently, it is configured to connect only to the market channel.
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
    token_filters = {"outcome": "Yes"}
    market_token_ids = load_market_token_ids(filepath=TOKENS_FILE, filters=token_filters)
    market_client = MarketWSSClient(assets_ids=market_token_ids)
    
    try:
        asyncio.run(market_client.run())
    except KeyboardInterrupt:
        logger.info("Market WebSocket client stopped by user.")

# --- Future Extension ---
# To connect to both the market and user channels, you can use the top-level Wsockt manager.
