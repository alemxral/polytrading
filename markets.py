import requests
import logging

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PolymarketFetcher:
    def __init__(self, endpoint="https://clob.polymarket.com/markets"):
        self.endpoint = endpoint
        self.events = []

    def fetch_last_page(self):
        """
        Fetches only the last page of markets from Polymarket using next_cursor pagination.
        """
        last_markets = []
        next_cursor = ""  # Start with an empty cursor

        while True:
            params = {}
            if next_cursor:
                params["next_cursor"] = next_cursor

            logger.info(f"Fetching markets with next_cursor: '{next_cursor}'")
            try:
                response = requests.get(self.endpoint, params=params)
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Request error: {e}")
                break

            data = response.json()

            # Determine markets and next_cursor
            if isinstance(data, dict):
                markets = data.get("data", [])
                next_cursor = data.get("next_cursor", "")
            elif isinstance(data, list):
                markets = data
                next_cursor = ""
            else:
                logger.error("Unexpected data format received.")
                break

            if not markets:
                logger.info("No more markets found.")
                break

            # Keep only the last page
            last_markets = markets

            # Stop if no cursor or cursor indicates the end
            if not next_cursor or next_cursor == "LTE=":
                break

        self.events = last_markets
        logger.info(f"Markets on last page retrieved: {len(self.events)}")
        return self.events

    def save_to_json(self, filename="markets_last_page.json"):
        """
        Saves the last page of markets to a JSON file.
        """
        if not self.events:
            logger.warning("No markets data to save.")
            return
        try:
            with open(filename, "w") as f:
                import json
                json.dump(self.events, f, indent=2)
            logger.info(f"Saved last page markets to JSON file: {filename}")
        except Exception as e:
            logger.error(f"Error saving JSON: {e}")


if __name__ == "__main__":
    fetcher = PolymarketFetcher()
    fetcher.fetch_last_page()
    fetcher.save_to_json()
