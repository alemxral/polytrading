import os
import logging
import json
import pandas as pd
from dotenv import load_dotenv

# Import necessary classes and endpoints from the py_clob_client module.
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import (
    ApiCreds,
    OrderArgs,
    MarketOrderArgs,
    BookParams,
)

# Load environment variables from .env
load_dotenv()

class PolyMarket:
    def __init__(self):
        """
        Initialize the PolyMarket wrapper.

        Reads configuration values from environment variables:
          - HOST: The base URL for the CLOB API.
          - CHAIN_ID: The blockchain chain id (default: 137).
          - POLYGON_KEY: The private key for Polygon.
          - API_KEY, API_SECRET, API_PASSPHRASE: Level 2 API credentials.
          - SIGNATURE_TYPE: The signature type (default: 2).
          - FUNDER: The funder address.
          
        Instantiates the underlying ClobClient with these parameters.
        """
        self.host = os.getenv("HOST", "https://clob.polymarket.com/").rstrip("/")
        self.chain_id = int(os.getenv("CHAIN_ID", "137"))
        self.polygon_key = os.getenv("POLYGON_KEY")
        self.api_key = os.getenv("API_KEY")
        self.api_secret = os.getenv("API_SECRET")
        self.api_passphrase = os.getenv("API_PASSPHRASE")
        self.signature_type = int(os.getenv("SIGNATURE_TYPE", "2"))
        self.funder = os.getenv("FUNDER", "0xF937dBe9976Ac34157b30DD55BDbf248458F6b43")
        
        # Create API credentials instance.
        api_creds = ApiCreds(
            api_key=self.api_key,
            api_secret=self.api_secret,
            api_passphrase=self.api_passphrase,
        )
        
        # Instantiate the underlying ClobClient.
        self.client = ClobClient(
            host=self.host,
            chain_id=self.chain_id,
            key=self.polygon_key,
            creds=api_creds,
            signature_type=self.signature_type,
            funder=self.funder,
        )       
        
        # Set up logging.
        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO)

    # --------------------
    # Markets Endpoints
    # --------------------

    def get_markets(self, next_cursor=""):
        """
        Get available CLOB markets (paginated).

        HTTP Request:
            GET {clob-endpoint}/markets?next_cursor={next_cursor}

        Request Parameters:
            next_cursor (optional, string): Cursor to start with (empty means beginning).

        Response Format:
            {
                "limit": number,
                "count": number,
                "next_cursor": string,  // 'LTE=' means the end, empty means beginning
                "data": [Market, ...]
            }
        A Market object includes:
            - condition_id: string
            - question_id: string
            - tokens: Tokens[2]
            - rewards: Rewards
            - minimum_order_size: string
            - minimum_tick_size: string
            - description: string
            - category: string
            - end_date_iso: string
            - game_start_time: string
            - question: string
            - market_slug: string
            - min_incentive_size: string
            - max_incentive_spread: string
            - active: boolean
            - closed: boolean
            - seconds_delay: integer
            - icon: string
            - fpmm: string
        """
        try:
            response = self.client.get_markets(next_cursor=next_cursor)
            if isinstance(response, dict) and "data" in response:
                markets = response["data"]
            else:
                markets = response
            self.logger.info(f"Retrieved {len(markets)} markets")
            return markets
        except Exception as e:
            self.logger.error(f"Error getting markets: {e}")
            return None

    def get_sampling_markets(self, next_cursor=""):
        """
        Get available CLOB markets that have rewards enabled.

        HTTP Request:
            GET {clob-endpoint}/sampling-markets?next_cursor={next_cursor}

        Response Format:
            {
                "limit": number,
                "count": number,
                "next_cursor": string,
                "data": [Market, ...]  // Sampling markets
            }
        """
        try:
            resp = self.client.get_sampling_markets(next_cursor=next_cursor)
            self.logger.info("Retrieved sampling markets")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting sampling markets: {e}")
            return None

    def get_simplified_markets(self, next_cursor=""):
        """
        Get available CLOB markets expressed in a reduced schema.

        HTTP Request:
            GET {clob-endpoint}/simplified-markets?next_cursor={next_cursor}

        Response Format:
            {
                "limit": number,
                "count": number,
                "next_cursor": string,
                "data": [SimplifiedMarket, ...]
            }
        A SimplifiedMarket object includes:
            - condition_id: string
            - tokens: Tokens[2]
            - rewards: Rewards
            - min_incentive_size: string
            - max_incentive_spread: string
            - active: boolean
            - closed: boolean
        """
        try:
            resp = self.client.get_simplified_markets(next_cursor=next_cursor)
            self.logger.info("Retrieved simplified markets")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting simplified markets: {e}")
            return None

    def get_sampling_simplified_markets(self, next_cursor=""):
        """
        Get available CLOB markets expressed in a reduced schema that have rewards enabled.

        HTTP Request:
            GET {clob-endpoint}/sampling-simplified-markets?next_cursor={next_cursor}

        Response Format is similar to get_simplified_markets.
        """
        try:
            resp = self.client.get_sampling_simplified_markets(next_cursor=next_cursor)
            self.logger.info("Retrieved sampling simplified markets")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting sampling simplified markets: {e}")
            return None

    def get_market(self, condition_id):
        """
        Get a single CLOB market.

        HTTP Request:
            GET {clob-endpoint}/markets/{condition_id}

        Response Format:
            {
                "market": Market
            }
        """
        try:
            resp = self.client.get_market(condition_id)
            self.logger.info(f"Retrieved market for condition_id {condition_id}")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting market {condition_id}: {e}")
            return None

    # --------------------
    # Prices and Books Endpoints
    # --------------------

    def get_order_book(self, token_id):
        """
        Get an order book summary for a market.

        HTTP Request:
            GET {clob-endpoint}/book?token_id={token_id}

        Response Format:
            {
                "market": string,
                "asset_id": string,
                "hash": string,
                "timestamp": string,
                "bids": [OrderSummary, ...],
                "asks": [OrderSummary, ...]
            }
        """
        try:
            order_book = self.client.get_order_book(token_id)
            self.logger.info(f"Retrieved order book for token_id {token_id}")
            return order_book
        except Exception as e:
            self.logger.error(f"Error getting order book for token_id {token_id}: {e}")
            return None

    def get_order_books(self, params: list[BookParams]):
        """
        Get order book summaries for a set of markets.

        HTTP Request:
            POST {clob-endpoint}/books

        Request Payload:
            params: list of BookParams (each with token_id)
        Response Format:
            [Orderbook, ...]
        """
        try:
            resp = self.client.get_order_books(params)
            self.logger.info("Retrieved multiple order books")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting order books: {e}")
            return None

    def get_price(self, token_id, side):
        """
        Get the price for a market (best bid or best ask).

        HTTP Request:
            GET {clob-endpoint}/price?token_id={token_id}&side={side}

        Request Parameters:
            token_id: string (required)
            side: string ("BUY" or "SELL", required)

        Response Example:
            {"price": ".513"}
        """
        try:
            resp = self.client.get_price(token_id, side)
            self.logger.info(f"Retrieved price for token_id {token_id}, side {side}")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting price for token_id {token_id}, side {side}: {e}")
            return None

    def get_prices(self, params: list[BookParams]):
        """
        Get the prices for a group of markets.

        HTTP Request:
            POST {clob-endpoint}/prices

        Request Payload:
            params: list of BookParams (each with token_id and side)
        Response Format:
            {
              "[asset_id]": {
                  "BUY": "price",
                  "SELL": "price"
              },
              ...
            }
        """
        try:
            resp = self.client.get_prices(params)
            self.logger.info("Retrieved prices for multiple markets")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting prices: {e}")
            return None

    def get_midpoint(self, token_id):
        """
        Get the midpoint price for a market (halfway between best bid and ask).

        HTTP Request:
            GET {clob-endpoint}/midpoint?token_id={token_id}

        Response Example:
            {'mid': '0.55'}
        """
        try:
            resp = self.client.get_midpoint(token_id)
            self.logger.info(f"Retrieved midpoint for token_id {token_id}")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting midpoint for token_id {token_id}: {e}")
            return None

    def get_midpoints(self, params: list[BookParams]):
        """
        Get the midpoint prices for a set of markets.

        HTTP Request:
            POST {clob-endpoint}/midpoints

        Request Payload:
            params: list of BookParams (each with token_id)
        Response Format:
            {
              "[asset_id]": "mid_price",
              ...
            }
        """
        try:
            resp = self.client.get_midpoints(params)
            self.logger.info("Retrieved midpoints for multiple markets")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting midpoints: {e}")
            return None

    def get_spread(self, token_id):
        """
        Get the spread for a market.

        HTTP Request:
            GET {clob-endpoint}/spread?token_id={token_id}

        Response Example:
            {"spread": ".513"}
        """
        try:
            resp = self.client.get_spread(token_id)
            self.logger.info(f"Retrieved spread for token_id {token_id}")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting spread for token_id {token_id}: {e}")
            return None

    def get_spreads(self, params: list[BookParams]):
        """
        Get the spreads for a set of markets.

        HTTP Request:
            GET {clob-endpoint}/spread (or POST, depending on implementation)

        Request Payload:
            params: list of BookParams (each with token_id)
        Response Format:
            {
              "[asset_id]": "spread",
              ...
            }
        """
        try:
            resp = self.client.get_spreads(params)
            self.logger.info("Retrieved spreads for multiple markets")
            return resp
        except Exception as e:
            self.logger.error(f"Error getting spreads: {e}")
            return None

    # --------------------
    # Data Download Functions
    # --------------------

    def clean_markets_data(self, markets):
        """
        Convert raw market data into a pandas DataFrame and perform basic cleaning.
        
        - Lower-case all column names.
        """
        if not markets:
            self.logger.warning("No market data to clean.")
            return None
        df = pd.DataFrame(markets)
        df.columns = [col.strip().lower() for col in df.columns]
        return df

    @staticmethod
    def flatten_tokens(tokens):
        """
        Flatten the nested tokens field into a string.

        Each token dictionary is converted into a string with key fields:
            token_id, outcome, price, winner

        Tokens are joined with a " | " separator.
        """
        if not tokens or not isinstance(tokens, list):
            return ""
        flat_list = []
        for token in tokens:
            token_id = token.get("token_id", "")
            outcome = token.get("outcome", "")
            price = token.get("price", "")
            winner = token.get("winner", "")
            flat_str = f"token_id: {token_id}, outcome: {outcome}, price: {price}, winner: {winner}"
            flat_list.append(flat_str)
        return " | ".join(flat_list)

    def download_markets_data(self, mode="json"):
        """
        Download markets data and store it in the backend/data/ directory.

        mode:
            "json" - Saves the raw markets data as a JSON file.
            "csv"  - Cleans, filters (accepting_orders==True), flattens the tokens field,
                     and saves the data as a CSV file.
        """
        markets = self.get_markets()
        if markets is None:
            self.logger.error("No market data available for download.")
            return None

        # Ensure backend/data directory exists.
        data_dir = os.path.join("backend", "data")
        os.makedirs(data_dir, exist_ok=True)

        if mode.lower() == "json":
            filename = os.path.join(data_dir, "markets_data.json")
            try:
                with open(filename, "w") as f:
                    json.dump(markets, f, indent=2)
                self.logger.info(f"Markets data saved as JSON to {filename}")
                return filename
            except Exception as e:
                self.logger.error(f"Error saving JSON: {e}")
                return None
        elif mode.lower() == "csv":
            df = self.clean_markets_data(markets)
            # Filter for markets accepting orders.
            df_filtered = df[df["accepting_orders"] == True].copy()
            # Flatten the tokens column.
            df_filtered["tokens"] = df_filtered["tokens"].apply(PolyMarket.flatten_tokens)
            filename = os.path.join(data_dir, "markets_data.csv")
            try:
                df_filtered.to_csv(filename, index=False)
                self.logger.info(f"Markets data saved as CSV to {filename}")
                return filename
            except Exception as e:
                self.logger.error(f"Error saving CSV: {e}")
                return None
        else:
            self.logger.error("Unsupported mode provided. Use 'json' or 'csv'.")
            return None

    # --------------------
    # Orders and Trades Endpoints
    # --------------------

    def place_limit_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        fee_rate_bps: int = 0,
        nonce: int = 0,
        expiration: int = 0,
        taker: str = "0x0000000000000000000000000000000000000000",
    ):
        """
        Create and post a limit order.

        Level 1 authentication is required.

        Parameters:
            token_id: str - Market token identifier.
            price: float - Price at which to create the order.
            size: float - Order size.
            side: str - "BUY" or "SELL".
            fee_rate_bps: int - Fee rate in basis points.
            nonce: int - Nonce for onchain cancellations.
            expiration: int - Timestamp after which the order expires.
            taker: str - Order taker address (default is public order).

        Returns the API response.
        """
        try:
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                fee_rate_bps=fee_rate_bps,
                nonce=nonce,
                expiration=expiration,
                taker=taker,
            )
            order = self.client.create_order(order_args)
            response = self.client.post_order(order)
            self.logger.info("Limit order placed successfully.")
            return response
        except Exception as e:
            self.logger.error(f"Error placing limit order: {e}")
            return None

    def place_market_order(
        self,
        token_id: str,
        amount: float,
        side: str,
        price: float = None,
        fee_rate_bps: int = 0,
        nonce: int = 0,
        taker: str = "0x0000000000000000000000000000000000000000",
    ):
        """
        Create and post a market order.

        Level 1 authentication is required.

        Parameters:
            token_id: str - Market token identifier.
            amount: float - Amount (BUY: funds to use; SELL: shares to sell).
            side: str - "BUY" or "SELL".
            price: float (optional) - Price for the order (if not provided, market price is used).
            fee_rate_bps: int - Fee rate in basis points.
            nonce: int - Nonce for onchain cancellations.
            taker: str - Order taker address.

        Returns the API response.
        """
        try:
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=side,
                price=price,
                fee_rate_bps=fee_rate_bps,
                nonce=nonce,
                taker=taker,
            )
            order = self.client.create_market_order(order_args)
            response = self.client.post_order(order)
            self.logger.info("Market order placed successfully.")
            return response
        except Exception as e:
            self.logger.error(f"Error placing market order: {e}")
            return None

    def get_trade_history(self, params=None):
        """
        Retrieve the trade history for the authenticated user.

        Level 2 authentication is required.
        """
        try:
            trades = self.client.get_trades(params)
            self.logger.info("Trade history retrieved successfully.")
            return trades
        except Exception as e:
            self.logger.error(f"Error retrieving trade history: {e}")
            return None

# --------------------------
# Example usage / test code
# --------------------------
if __name__ == "__main__":
    pm = PolyMarket()
    
    # Example 1: Retrieve and display markets data.
    raw_markets = pm.get_markets()
    if raw_markets:
        df_markets = pm.clean_markets_data(raw_markets)
        print("First 5 Markets:")
        print(df_markets.head())
    
    # Example 2: Download markets data in JSON mode.
    json_file = pm.download_markets_data(mode="json")
    if json_file:
        print(f"\nJSON file '{json_file}' created successfully.")
    
    # Example 3: Download markets data in CSV mode.
    csv_file = pm.download_markets_data(mode="csv")
    if csv_file:
        print(f"\nCSV file '{csv_file}' created successfully.")
    
    # Example 4: Retrieve order book for a sample market.
    if raw_markets:
        sample_market = raw_markets[0]
        # Assume 'condition_id' represents the market token identifier.
        token_id = sample_market.get("condition_id")
        if token_id:
            order_book = pm.get_order_book(token_id)
            print("\nOrder Book for Token:", token_id)
            print(json.dumps(order_book, indent=2))
    
    # Example 5: Retrieve simplified markets.
    simplified = pm.get_simplified_markets()
    if simplified:
        print("\nSimplified Markets:")
        print(json.dumps(simplified, indent=2))
    
    # Example 6: Retrieve a single market by condition_id.
    if raw_markets:
        sample_market = raw_markets[0]
        condition_id = sample_market.get("condition_id")
        if condition_id:
            market_details = pm.get_market(condition_id)
            print("\nMarket Details:")
            print(json.dumps(market_details, indent=2))
    
    # Example 7: Retrieve price for a market.
    if raw_markets:
        sample_market = raw_markets[0]
        token_id = sample_market.get("condition_id")
        if token_id:
            price_resp = pm.get_price(token_id, side="BUY")
            print("\nPrice for Token (BUY):")
            print(price_resp)
    
    # Example 8: Retrieve midpoint for a market.
    if raw_markets:
        sample_market = raw_markets[0]
        token_id = sample_market.get("condition_id")
        if token_id:
            midpoint_resp = pm.get_midpoint(token_id)
            print("\nMidpoint for Token:")
            print(midpoint_resp)
    
    # Example 9: Retrieve spread for a market.
    if raw_markets:
        sample_market = raw_markets[0]
        token_id = sample_market.get("condition_id")
        if token_id:
            spread_resp = pm.get_spread(token_id)
            print("\nSpread for Token:")
            print(spread_resp)
    
    # Further examples for get_prices, get_midpoints, get_spreads, etc. can be added similarly.


    

print(
    
    pm.get_order_book(
        "59719086471851132118057103160039200789268717383832814315021216098909788743101"
    )
)
