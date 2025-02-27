import os
import logging
import json
import pandas as pd
import requests
from dotenv import load_dotenv
from initialize_client import default_client

# Configure minimal logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MarketDownloader")

# Use the pre-initialized client
client = default_client

# The hosted endpoint for markets (assumed to be at /markets on the client host)
markets_endpoint = f"{client.host}/markets"

all_markets = []
next_cursor = ""  # Start with an empty next_cursor

while True:
    params = {}
    if next_cursor:
        params["next_cursor"] = next_cursor

    logger.info(f"Fetching markets with next_cursor: '{next_cursor}'")
    response = requests.get(markets_endpoint, params=params)
    
    if response.status_code != 200:
        logger.error(f"Failed to fetch markets: {response.status_code} {response.text}")
        break

    data = response.json()
    
    # Expecting a dict with 'data' and 'next_cursor'; if a list is returned, use it directly.
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

    all_markets.extend(markets)
    
    # Stop if there's no next_cursor or if it indicates the end (e.g., "LTE=")
    if not next_cursor or next_cursor == "LTE=":
        break

logger.info(f"Total markets retrieved: {len(all_markets)}")

# Save the complete JSON data to a file.
with open("markets_all.json", "w") as f:
    json.dump(all_markets, f, indent=2)

# Convert the data to a pandas DataFrame and export as CSV.
df = pd.DataFrame(all_markets)
csv_filename = "markets_all.csv"
df.to_csv(csv_filename, index=False)
logger.info(f"CSV file '{csv_filename}' created successfully with {len(all_markets)} records.")
