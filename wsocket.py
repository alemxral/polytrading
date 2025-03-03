import asyncio
import websockets
import json
import logging
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

# --- Configuration & Logging ---
load_dotenv()  # Load environment variables from .env if available
logger = logging.getLogger("Wsockt")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
TOKENS_FILE = "tokens_premier_league.json"

def load_market_token_ids(filepath=TOKENS_FILE, filters=None):
    if not os.path.exists(filepath):
        logger.error(f"Token file '{filepath}' not found.")
        return []
    try:
        with open(filepath, "r") as f:
            tokens = json.load(f)
        if filters:
            tokens = [t for t in tokens if all(t.get(k) == v for k, v in filters.items())]
            logger.debug(f"Filtered tokens: {len(tokens)} match filters {filters}.")
        token_ids = [token.get("token_id") for token in tokens if token.get("token_id")]
        logger.info(f"Loaded {len(token_ids)} token IDs from '{filepath}'.")
        return token_ids
    except Exception as e:
        logger.error(f"Error loading tokens from {filepath}: {e}")
        return []


# --- Base WebSocket Client Class ---
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
            logger.info(f"[{self.channel_type.upper()}] Sent subscription message: {sub_msg}")
        except Exception as e:
            logger.error(f"[{self.channel_type.upper()}] Failed to send subscription message: {e}")

    async def listen(self):
        # No file I/O here for each message.
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
        raise NotImplementedError("Subclasses must implement handle_message()")

    async def run(self):
        await self.connect()
        await self.subscribe()
        await asyncio.gather(
            self.listen(),
            self.save_token_data(),
            self.investment_strategy_monitor(interval=2)
        )


# --- OrderSender Class ---
class OrderSender:
    @staticmethod
    async def send_order(token_id, order_size, order_price, weighted=False):
        try:
            logger.info(f"OrderSender: Sending order for token {token_id} at price {order_price} for size {order_size} (weighted: {weighted}).")
            await asyncio.sleep(0.1)
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
    def __init__(self, assets_ids, ws_url=WS_URL):
        super().__init__(ws_url, channel_type="market")
        self.assets_ids = assets_ids
        self.token_data = {}  # In-memory storage

    def build_subscription_message(self):
        return {"assets_ids": self.assets_ids, "type": "market"}

    def extract_best_level(self, levels, is_ask=True):
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
                    if price < best_price or (price == best_price and size > best_size):
                        best_level = level
                else:
                    if price > best_price or (price == best_price and size > best_size):
                        best_level = level
        if best_level is None:
            return "", ""
        return best_level.get("price", ""), best_level.get("size", "")


    async def handle_message(self, message):
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
                "old_tick_size": "0.001",
                "new_tick_size": "0.001"
            }
        # Update logs.
        self.token_data[asset_id]["logs"][event_type] = timestamp

        if event_type == "book":
            market = message.get("market", self.token_data[asset_id].get("market", ""))
            bids = message.get("bids", [])
            asks = message.get("asks", [])
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
            logger.info(f"[MARKET BOOK] Asset {asset_id} updated: best bid {best_bid} (size {best_bid_size}), best ask {best_sell} (size {best_sell_size})")
        elif event_type == "price_change":
            # (Your existing price_change handling code goes here.)
            pass
        elif event_type == "tick_size_change":
            old_tick = message.get("old_tick_size", "0.001")
            new_tick = message.get("new_tick_size", "0.001")
            self.token_data[asset_id].update({
                "timestamp": timestamp,
                "old_tick_size": old_tick,
                "new_tick_size": new_tick
            })
            logger.info(f"[MARKET TICK SIZE CHANGE] Updated tick sizes for asset {asset_id}: old {old_tick}, new {new_tick}")
        elif event_type == "last_trade_price":
            logger.info(f"[LAST TRADE PRICE] Received message for asset {asset_id}: {message}")
            # Log the last_trade_price message into a JSON file.
            log_file = "last_trade_price_log.json"
            try:
                if os.path.exists(log_file):
                    with open(log_file, "r") as f:
                        trade_log = json.load(f)
                        if not isinstance(trade_log, list):
                            trade_log = []
                else:
                    trade_log = []
            except Exception as e:
                logger.error(f"Error reading last trade price log: {e}")
                trade_log = []
            trade_log.append({
                "timestamp": timestamp,
                "asset_id": asset_id,
                "message": message
            })
            try:
                with open(log_file, "w") as f:
                    json.dump(trade_log, f, indent=4)
                logger.info("[LAST TRADE PRICE] Log updated.")
            except Exception as e:
                logger.error(f"Error writing last trade price log: {e}")
        else:
            logger.info(f"[MARKET] Unhandled message type: {event_type}")



    async def investment_strategy_monitor(self, interval=2):
        """
        Continuously computes the total best ask price and optimal size across tokens based on the latest in-memory data.
        Logs the computed total price and optimal size every iteration.
        When total best ask price is below 1, it sends a group order.
        To reduce I/O overhead, the analysis log is written to disk every 5 iterations.
        """
        analysis_log_file = "analysis_log.json"
        order_log_file = "order_log.json"
        iteration = 0  # Counter to throttle file writes

        while True:
            orders = []
            log_orders = []
            token_sizes = []
            standalone_prices = {}
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
                except Exception as e:
                    logger.error(f"Error processing token {token_id}: {e}")
                    continue
                if best_sell_price is None or best_sell_size is None:
                    continue
                try:
                    tick_size = float(data.get("new_tick_size", "0.001"))
                except Exception:
                    tick_size = 0.001
                if best_sell_price <= tick_size:
                    logger.warning(f"Token {token_id} best ask price {best_sell_price} is not greater than tick size {tick_size}.")
                    continue
                orders.append({
                    "token_id": token_id,
                    "price": best_sell_price,
                    "size": best_sell_size,
                    "optimal_size": None
                })
                log_orders.append({
                    "token_id": token_id,
                    "best_sell_price": best_sell_price,
                    "best_sell_size": best_sell_size
                })
                standalone_prices.setdefault(token_id, []).append({"price": best_sell_price})
                token_sizes.append(best_sell_size)
            total_price = sum(
                entry["price"]
                for price_list in standalone_prices.values()
                for entry in price_list
            )
            optimal_size = min(token_sizes) if token_sizes else 0
            logger.info(f"[INVESTMENT STRATEGY] Total best ask price: {total_price}, Optimal size: {optimal_size}")
            iteration += 1
            # Throttle analysis log file writes every 5 iterations
            if iteration % 5 == 0:
                call_timestamp = datetime.now().isoformat() + "Z"
                analysis_entry = {
                    "timestamp": call_timestamp,
                    "log_orders": log_orders,
                    "total_price": total_price,
                    "optimal_size": optimal_size
                }
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
                analysis_data.append(analysis_entry)
                try:
                    with open(analysis_log_file, "w") as f:
                        json.dump(analysis_data, f, indent=4)
                    logger.info("[INVESTMENT STRATEGY] Analysis log updated.")
                except Exception as e:
                    logger.error(f"Error writing analysis log: {e}")
            if total_price < 1 and orders:
                for order in orders:
                    order["optimal_size"] = optimal_size
                for order in orders:
                    logger.info(f"[INVESTMENT STRATEGY] Order for token {order['token_id']}: original size {order['size']}, optimal size {order['optimal_size']}, price {order['price']}")
                order_id = str(uuid.uuid4())
                order_timestamp = datetime.utcnow().isoformat() + "Z"
                wrapped_order = {
                    "order_id": order_id,
                    "timestamp": order_timestamp,
                    "total_price": total_price,
                    "orders": orders
                }
                try:
                    if os.path.exists(order_log_file):
                        with open(order_log_file, "r") as f:
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
                    with open(order_log_file, "w") as f:
                        json.dump(existing_orders, f, indent=4)
                    logger.info(f"[INVESTMENT STRATEGY] Order log updated. New order id: {order_id} with optimal size: {optimal_size} and total_price: {total_price}")
                except Exception as e:
                    logger.error(f"Error saving order log: {e}")
                send_tasks = []
                for order in orders:
                    token_id = order["token_id"]
                    order_size = order["optimal_size"]
                    order_price = order["price"]
                    weighted = order["size"] != order["optimal_size"]
                    send_tasks.append(OrderSender.send_order(token_id, order_size, order_price, weighted))
                responses = await asyncio.gather(*send_tasks)
                logger.info(f"[INVESTMENT STRATEGY] Order sending responses: {responses}")
            await asyncio.sleep(interval)

    async def save_token_data(self, filepath="market_data.json", interval=5):
        while True:
            try:
                with open(filepath, "w") as f:
                    json.dump(self.token_data, f, indent=2)
                logger.info(f"Saved token data to {filepath}.")
            except Exception as e:
                logger.error(f"Error saving token data: {e}")
            await asyncio.sleep(interval)

    async def run(self):
        await self.connect()
        await self.subscribe()
        await asyncio.gather(
            self.listen(),
            self.save_token_data(),
            self.investment_strategy_monitor(interval=2)
        )


class UserWSSClient(BaseWSSClient):
    def __init__(self, markets, auth, ws_url=WS_URL):
        super().__init__(ws_url, channel_type="user")
        self.markets = markets
        self.auth = auth
        self.order_book_data = {}

    def build_subscription_message(self):
        return {"auth": self.auth, "markets": self.markets, "type": "user"}

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


class Wsockt:
    def __init__(self, tokens_filepath=TOKENS_FILE, token_filters=None):
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


if __name__ == "__main__":
    token_filters = {"outcome": "Yes"}
    market_token_ids = load_market_token_ids(filepath=TOKENS_FILE, filters=token_filters)
    market_client = MarketWSSClient(assets_ids=market_token_ids)
    try:
        asyncio.run(market_client.run())
    except KeyboardInterrupt:
        logger.info("Market WebSocket client stopped by user.")
