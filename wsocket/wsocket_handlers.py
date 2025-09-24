import json
import os
import logging

logger = logging.getLogger("MarketMessageHandler")
logger.setLevel(logging.DEBUG)

# ---------- Base Handler for Market Messages ----------
class MarketMessageHandler:
    """
    Base class for market message handlers.
    
    Parameters:
      - fields: List of fields to extract from the message.
      - save_to_file: Boolean flag; if True, save the processed message.
      - file_path: Path to a JSON file for saving.
    """
    def __init__(self, fields=None, save_to_file=False, file_path=None):
        self.fields = fields or []
        self.save_to_file = save_to_file
        self.file_path = file_path

    def process(self, message):
        extracted = {field: self._parse_field(message.get(field)) for field in self.fields}
        if self.save_to_file and self.file_path:
            try:
                data = []
                if os.path.exists(self.file_path):
                    with open(self.file_path, "r") as f:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                data.append(extracted)
                with open(self.file_path, "w") as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                logger.error(f"Error writing to {self.file_path}: {e}")
        return extracted

    def _parse_field(self, field):
        """
        Ensures that the field is always returned as a list if it is a dict or list.
        Otherwise, returns the field unchanged.
        """
        if isinstance(field, list):
            return field
        elif isinstance(field, dict):
            return [field]
        else:
            return field

# ---------- Book Message Handler and Related Classes ----------

logger = logging.getLogger("BookMessage")
logger.setLevel(logging.DEBUG)

class OrderSummary:
    """Represents one level of an order book."""
    def __init__(self, price, size):
        try:
            self.price = float(price)
        except Exception:
            self.price = 0.0
        try:
            self.size = float(size)
        except Exception:
            self.size = 0.0

    def __repr__(self):
        return f"OrderSummary(price={self.price}, size={self.size})"

class BookMessage:
    """
    Represents a "book" message and supports updates via price_change or tick_size_change messages.
    """
    def __init__(self, message):
        self.event_type = message.get("event_type")
        self.asset_id = message.get("asset_id")
        self.market = message.get("market")
        self.timestamp = message.get("timestamp")
        self.hash = message.get("hash")
        self.tick_size = 0.01  # default tick size; can be updated
        self.buys = self._parse_order_summaries(message.get("buys"))
        self.sells = self._parse_order_summaries(message.get("sells"))
        self.last_trade_price = None  # last trade price (if provided)
        self.history = []  # time series of best prices

    def _parse_order_summaries(self, data):
        summaries = []
        # If data is a list, process each element; if it's a dict, wrap it.
        if isinstance(data, list):
            for item in data:
                try:
                    summaries.append(OrderSummary(item.get("price"), item.get("size")))
                except Exception as e:
                    logger.error(f"Error parsing order summary from item {item}: {e}")
        elif isinstance(data, dict):
            try:
                summaries.append(OrderSummary(data.get("price"), data.get("size")))
            except Exception as e:
                logger.error(f"Error parsing order summary from dict {data}: {e}")
        else:
            logger.warning(f"Unexpected type for order summaries: {type(data)}")
        return summaries

    def update_last_trade_price(self, message):
        try:
            self.last_trade_price = float(message.get("price", self.last_trade_price or 0))
            logger.info(f"[BookMessage] Last trade price updated to {self.last_trade_price} for asset {self.asset_id}")
        except Exception as e:
            logger.error(f"Error updating last trade price for asset {self.asset_id}: {e}")

    def update_price_change(self, message):
        """
        Updates the book with a price_change message.
        Expects message to have "changes" (a list of dicts with "price", "side", "size")
        and a "timestamp".
        """
        changes = message.get("changes", [])
        for change in changes:
            try:
                change_price = float(change.get("price", 0))
                change_size = float(change.get("size", 0))
                side = change.get("side", "").lower()
            except Exception as e:
                logger.error(f"Error parsing price change: {e}")
                continue

            if side == "sell":
                updated = False
                for order in self.sells:
                    if abs(order.price - change_price) < 0.0001:
                        order.size = change_size
                        updated = True
                        break
                if not updated:
                    self.sells.append(OrderSummary(change_price, change_size))
            elif side == "buy":
                updated = False
                for order in self.buys:
                    if abs(order.price - change_price) < 0.0001:
                        order.size = change_size
                        updated = True
                        break
                if not updated:
                    self.buys.append(OrderSummary(change_price, change_size))
        self.timestamp = message.get("timestamp", self.timestamp)
        logger.info(f"[BookMessage] Price change updated for asset {self.asset_id} at {self.timestamp}")

    def update_tick_size_change(self, message):
        try:
            new_tick = float(message.get("new_tick_size", self.tick_size))
            self.tick_size = new_tick
            self.timestamp = message.get("timestamp", self.timestamp)
            logger.info(f"[BookMessage] Tick size updated to {self.tick_size} for asset {self.asset_id}")
        except Exception as e:
            logger.error(f"Error updating tick size for asset {self.asset_id}: {e}")

    # Additional helper functions:
    def get_total_size_for_side(self, side, price, tolerance=0.0001):
        total = 0.0
        side = side.lower()
        orders = self.buys if side == "buy" else self.sells
        for order in orders:
            if abs(order.price - price) < tolerance:
                total += order.size
        return total

    def get_size_for_price(self, side, price, tolerance=0.0001):
        side = side.lower()
        orders = self.buys if side == "buy" else self.sells
        for order in orders:
            if abs(order.price - price) < tolerance:
                return order.size
        return None

    def extract_best_buy(self):
        if not self.buys:
            return None, 0
        best = max(self.buys, key=lambda o: o.price)
        return best.price, best.size

    def extract_best_sell(self):
        if not self.sells:
            return None, 0
        best = min(self.sells, key=lambda o: o.price)
        return best.price, best.size

    def record_best_prices(self):
        best_bid, _ = self.extract_best_buy()
        best_ask, _ = self.extract_best_sell()
        entry = {
            "timestamp": datetime.now().isoformat() + "Z",
            "best_bid": best_bid,
            "best_ask": best_ask
        }
        self.history.append(entry)
        return entry

    def get_time_series(self):
        return self.history

    def get_top_buy_levels(self, n=1):
        return sorted(self.buys, key=lambda o: o.price, reverse=True)[:n]

    def get_top_sell_levels(self, n=1):
        return sorted(self.sells, key=lambda o: o.price)[:n]

    def aggregated_buy_size(self):
        return sum(o.size for o in self.buys)

    def aggregated_sell_size(self):
        return sum(o.size for o in self.sells)

    def __repr__(self):
        return (f"BookMessage(asset_id={self.asset_id}, market={self.market}, timestamp={self.timestamp}, "
                f"tick_size={self.tick_size}, buys={self.buys}, sells={self.sells}, history={self.history})")

class BookMessageHandler(MarketMessageHandler):
    def __init__(self, save_to_file=False, file_path="book_messages.json"):
        fields = ["event_type", "asset_id", "market", "timestamp", "hash", "buys", "sells"]
        super().__init__(fields=fields, save_to_file=save_to_file, file_path=file_path)
    
    def process(self, message):
        book_msg = BookMessage(message)
        # For demonstration, extract the top 3 levels and aggregated sizes.
        result = {
            "asset_id": book_msg.asset_id,
            "market": book_msg.market,
            "timestamp": book_msg.timestamp,
            "hash": book_msg.hash,
            "top_buys": [vars(o) for o in book_msg.get_top_buy_levels(3)],
            "top_sells": [vars(o) for o in book_msg.get_top_sell_levels(3)],
            "aggregated_buy_size": book_msg.aggregated_buy_size(),
            "aggregated_sell_size": book_msg.aggregated_sell_size()
        }
        if self.save_to_file and self.file_path:
            try:
                data = []
                if os.path.exists(self.file_path):
                    with open(self.file_path, "r") as f:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                data.append(result)
                with open(self.file_path, "w") as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                logger.error(f"Error writing book message log: {e}")
        return book_msg

# -------------------- Price Change Message Handler --------------------
class PriceChangeMessageHandler(MarketMessageHandler):
    def __init__(self, save_to_file=False, file_path="price_change_messages.json"):
        fields = ["event_type", "asset_id", "market", "price", "size", "side", "timestamp", "hash"]
        super().__init__(fields=fields, save_to_file=save_to_file, file_path=file_path)

# -------------------- Tick Size Change Message Handler --------------------
class TickSizeChangeMessageHandler(MarketMessageHandler):
    def __init__(self, save_to_file=False, file_path="tick_size_change_messages.json"):
        fields = ["event_type", "asset_id", "market", "old_tick_size", "new_tick_size", "timestamp"]
        super().__init__(fields=fields, save_to_file=save_to_file, file_path=file_path)

# -------------------- Last Trade Price Message Handler --------------------
class LastTradePriceMessageHandler(MarketMessageHandler):
    def __init__(self, save_to_file=False, file_path="last_trade_price_messages.json"):
        fields = ["event_type", "asset_id", "market", "timestamp"]
        super().__init__(fields=fields, save_to_file=save_to_file, file_path=file_path)

# -------------------- User Channel Handlers --------------------

class UserMessageHandler:
    """
    Base handler for user channel messages.
    """
    def __init__(self, fields=None, save_to_file=False, file_path=None):
        self.fields = fields or []
        self.save_to_file = save_to_file
        self.file_path = file_path

    def process(self, message):
        extracted = {field: message.get(field) for field in self.fields}
        if self.save_to_file and self.file_path:
            try:
                data = []
                if os.path.exists(self.file_path):
                    with open(self.file_path, "r") as f:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                data.append(extracted)
                with open(self.file_path, "w") as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                logger.error(f"Error writing to {self.file_path}: {e}")
        return extracted

# -------------------- MakerOrder and Trade Message Handler --------------------
class MakerOrder:
    """
    Represents a maker order in a trade message.
    """
    def __init__(self, data):
        try:
            self.asset_id = data.get("asset_id")
            self.matched_amount = data.get("matched_amount")
            self.order_id = data.get("order_id")
            self.outcome = data.get("outcome")
            self.owner = data.get("owner")
            self.price = data.get("price")
        except Exception as e:
            logger.error(f"Error parsing MakerOrder: {e}")

    def to_dict(self):
        return {
            "asset_id": self.asset_id,
            "matched_amount": self.matched_amount,
            "order_id": self.order_id,
            "outcome": self.outcome,
            "owner": self.owner,
            "price": self.price
        }

    def __repr__(self):
        return f"MakerOrder(order_id={self.order_id}, price={self.price}, matched_amount={self.matched_amount})"

class TradeMessage:
    """
    Parses a "trade" message.
    """
    def __init__(self, message):
        self.asset_id = message.get("asset_id")
        self.event_type = message.get("event_type")
        self.trade_id = message.get("id")
        self.last_update = message.get("last_update")
        self.market = message.get("market")
        self.matchtime = message.get("matchtime")
        self.outcome = message.get("outcome")
        self.owner = message.get("owner")
        self.price = message.get("price")
        self.side = message.get("side")
        self.size = message.get("size")
        self.status = message.get("status")
        self.taker_order_id = message.get("taker_order_id")
        self.timestamp = message.get("timestamp")
        self.trade_owner = message.get("trade_owner")
        self.type = message.get("type")
        self.maker_orders = self._parse_maker_orders(message.get("maker_orders"))

    def _parse_maker_orders(self, data):
        orders = []
        if isinstance(data, list):
            for item in data:
                try:
                    orders.append(MakerOrder(item))
                except Exception as e:
                    logger.error(f"Error parsing maker order: {e}")
        elif isinstance(data, dict):
            try:
                orders.append(MakerOrder(data))
            except Exception as e:
                logger.error(f"Error parsing maker order dict: {e}")
        else:
            logger.warning(f"Unexpected type for maker_orders: {type(data)}")
        return orders

    def get_maker_order_fields(self, order_id, fields):
        for order in self.maker_orders:
            if order.order_id == order_id:
                result = {}
                for field in fields:
                    result[field] = getattr(order, field, None)
                return result
        return None

    def __repr__(self):
        return (f"TradeMessage(trade_id={self.trade_id}, asset_id={self.asset_id}, price={self.price}, "
                f"side={self.side}, size={self.size}, status={self.status}, maker_orders={self.maker_orders})")

class TradeMessageHandler(UserMessageHandler):
    def __init__(self, save_to_file=False, file_path="trade_messages.json"):
        fields = [
            "asset_id", "event_type", "id", "last_update", "market",
            "matchtime", "outcome", "owner", "price", "side",
            "size", "status", "taker_order_id", "timestamp", "trade_owner", "type", "maker_orders"
        ]
        super().__init__(fields=fields, save_to_file=save_to_file, file_path=file_path)
    
    def process(self, message):
        trade_msg = TradeMessage(message)
        result = {
            "trade_id": trade_msg.trade_id,
            "asset_id": trade_msg.asset_id,
            "price": trade_msg.price,
            "side": trade_msg.side,
            "size": trade_msg.size,
            "status": trade_msg.status,
            "maker_orders": [order.to_dict() for order in trade_msg.maker_orders]
        }
        if self.save_to_file and self.file_path:
            try:
                data = []
                if os.path.exists(self.file_path):
                    with open(self.file_path, "r") as f:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                data.append(result)
                with open(self.file_path, "w") as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                logger.error(f"Error writing trade message log: {e}")
        return trade_msg

# -------------------- Order Message Handler --------------------
class OrderMessageHandler(UserMessageHandler):
    def __init__(self, save_to_file=False, file_path="order_messages.json"):
        fields = [
            "asset_id", "associate_trades", "event_type", "id", "market",
            "order_owner", "original_size", "outcome", "owner", "price",
            "side", "size_matched", "timestamp", "type"
        ]
        super().__init__(fields=fields, save_to_file=save_to_file, file_path=file_path)
