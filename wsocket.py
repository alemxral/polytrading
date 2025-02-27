import asyncio
import websockets
import json
import logging
import csv
import os

# --- Configuration and Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MarketTableUpdater")

# WebSocket endpoint for market data
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# File names
PAIRED_TOKENS_FILE = "paired_tokens.json"  # Contains initial paired token data
CSV_OUTPUT = "market_table.csv"

# --- In-Memory Table Structure ---
# We'll build a table keyed by question_id (market id).
# Each value is a dict with:
#   - "market_slug": string
#   - "tokens": dict keyed by token_id, each with:
#         outcome, timestamp, best_bids (list of dicts), best_asks (list of dicts)
market_table = {}

def build_initial_table():
    """
    Build the initial market table from paired_tokens.json.
    Each record in that file should have:
      "question_id", "market_slug", "yes_token", "no_token"
    Each token object should include at least "token_id", "outcome".
    """
    if not os.path.exists(PAIRED_TOKENS_FILE):
        logger.error(f"Paired tokens file '{PAIRED_TOKENS_FILE}' not found.")
        return

    try:
        with open(PAIRED_TOKENS_FILE, "r") as f:
            paired_markets = json.load(f)
    except Exception as e:
        logger.error(f"Error reading paired tokens file: {e}")
        return

    for market in paired_markets:
        question_id = market.get("question_id")
        market_slug = market.get("market_slug", "")
        if not question_id:
            continue

        market_table[question_id] = {
            "market_slug": market_slug,
            "tokens": {}  # to store tokens keyed by token_id
        }
        for side in ["yes_token", "no_token"]:
            token_obj = market.get(side)
            if token_obj:
                token_id = token_obj.get("token_id")
                outcome = token_obj.get("outcome", "")
                if token_id:
                    # Initialize with empty market data fields.
                    market_table[question_id]["tokens"][token_id] = {
                        "outcome": outcome,
                        "timestamp": "",
                        "best_bids": [],   # list of dicts: [{"price": ..., "size": ...}, ...]
                        "best_asks": []    # list of dicts: [{"price": ..., "size": ...}, ...]
                    }
    logger.info(f"Built initial market table for {len(market_table)} market(s).")

def get_all_token_ids():
    """
    Extract a flat list of all token_ids from the initial market table.
    """
    token_ids = []
    for market in market_table.values():
        token_ids.extend(list(market["tokens"].keys()))
    return token_ids

def update_market_table(msg):
    """
    Update the in-memory market_table based on an incoming websocket message.
    
    For a "book" event, update the record for the corresponding token with:
      - timestamp
      - up to three best bids and three best asks (if available)
    
    For a "price_change" event, update the timestamp.
    
    If msg is a list, iterate over its elements.
    
    Expected structure for a book message:
    {
      "market": "<question_id>",
      "asset_id": "<token_id>",
      "timestamp": "1740691280147",
      "bids": [ { "price": "0.001", "size": "1883481.09" }, { "price": "0.002", "size": "1045404.32" }, ... ],
      "asks": [ { "price": "0.999", "size": "11000000" }, { "price": "0.97", "size": "4250" }, ... ],
      "event_type": "book"
    }
    """
    if isinstance(msg, list):
        for m in msg:
            update_market_table(m)
        return

    event_type = msg.get("event_type")
    market_id = msg.get("market")
    if not market_id or market_id not in market_table:
        logger.debug(f"Market {market_id} not found in table. Ignoring message.")
        return

    if event_type == "book":
        asset_id = msg.get("asset_id")
        timestamp = msg.get("timestamp", "")
        bids = msg.get("bids", [])
        asks = msg.get("asks", [])
        # Take the top three bids and asks (if available)
        best_bids = bids[:3] if bids else []
        best_asks = asks[:3] if asks else []
        if asset_id in market_table[market_id]["tokens"]:
            market_table[market_id]["tokens"][asset_id].update({
                "timestamp": timestamp,
                "best_bids": best_bids,
                "best_asks": best_asks
            })
            logger.info(f"Updated market {market_id} for token {asset_id} with book data.")
    elif event_type == "price_change":
        timestamp = msg.get("timestamp", "")
        asset_id = msg.get("asset_id")
        if asset_id and asset_id in market_table[market_id]["tokens"]:
            market_table[market_id]["tokens"][asset_id]["timestamp"] = timestamp
            logger.info(f"Updated market {market_id} for token {asset_id} with price_change timestamp.")
        else:
            # If asset_id not provided, update all tokens in the market.
            for tid in market_table[market_id]["tokens"]:
                market_table[market_id]["tokens"][tid]["timestamp"] = timestamp
            logger.info(f"Updated market {market_id} for all tokens with price_change timestamp.")

async def websocket_listener():
    """
    Connect to the websocket endpoint, subscribe using all token IDs, and update the table as messages are received.
    """
    all_token_ids = get_all_token_ids()
    subscribe_msg = {
        "assets_ids": all_token_ids,
        "type": "market"
    }
    try:
        async with websockets.connect(WS_URL) as websocket:
            await websocket.send(json.dumps(subscribe_msg))
            logger.info(f"Sent subscription message: {subscribe_msg}")

            while True:
                try:
                    msg = await websocket.recv()
                    data = json.loads(msg)
                    logger.info(f"Received message: {data}")
                    update_market_table(data)
                except Exception as e:
                    logger.error(f"Error receiving or processing message: {e}")
                    break
    except Exception as conn_err:
        logger.error(f"Websocket connection failed: {conn_err}")

async def table_writer(interval=10):
    """
    Periodically writes the in-memory market_table to a CSV file.
    Each row corresponds to one token in a market.
    Only writes rows that have been updated (i.e. at least one of best bids or asks is non-empty).
    """
    header = [
        "question_id", "market_slug", "token_id", "outcome", "timestamp",
        "bid1", "bid1_size", "bid2", "bid2_size", "bid3", "bid3_size",
        "ask1", "ask1_size", "ask2", "ask2_size", "ask3", "ask3_size"
    ]
    while True:
        await asyncio.sleep(interval)
        rows = []
        for question_id, info in market_table.items():
            market_slug = info.get("market_slug", "")
            for token_id, token_data in info.get("tokens", {}).items():
                # Only add row if any bid or ask info is present
                bids = token_data.get("best_bids", [])
                asks = token_data.get("best_asks", [])
                if not (bids or asks):
                    continue

                # Prepare bid columns (up to 3 bids)
                bid_cols = []
                for i in range(3):
                    if i < len(bids):
                        bid_cols.extend([bids[i].get("price", ""), bids[i].get("size", "")])
                    else:
                        bid_cols.extend(["", ""])
                # Prepare ask columns (up to 3 asks)
                ask_cols = []
                for i in range(3):
                    if i < len(asks):
                        ask_cols.extend([asks[i].get("price", ""), asks[i].get("size", "")])
                    else:
                        ask_cols.extend(["", ""])
                row = [
                    question_id,
                    market_slug,
                    token_id,
                    token_data.get("outcome", ""),
                    token_data.get("timestamp", "")
                ] + bid_cols + ask_cols
                rows.append(row)
        if rows:
            try:
                with open(CSV_OUTPUT, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    writer.writerows(rows)
                logger.info(f"Saved market table with {len(rows)} row(s) to {CSV_OUTPUT}")
            except Exception as e:
                logger.error(f"Error saving CSV: {e}")
        else:
            logger.info("Market table is empty; nothing to save.")

async def main():
    build_initial_table()
    listener_task = asyncio.create_task(websocket_listener())
    writer_task = asyncio.create_task(table_writer(10))
    await asyncio.gather(listener_task, writer_task)

if __name__ == "__main__":
    import csv
    asyncio.run(main())
