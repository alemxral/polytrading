import logging
import json
import requests
from ClobClientWrapper import default_client  # Pre-initialized client if needed elsewhere

# Configure minimal logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MarketDownloader")

# Gamma API endpoint URL for events (adjust if you prefer markets)
GAMMA_API_ENDPOINT = "https://gamma-api.polymarket.com/events"

# Query parameters for the API request (adjust limit, offset, and filters as needed)
params = {
    "limit": 10,   # Fetch 100 records per request
    "offset": 0,    # Starting offset for pagination
    "active": True  # Example filter: only active events/markets
}

all_records = []

while True:
    response = requests.get(GAMMA_API_ENDPOINT, params=params)
    
    if response.status_code != 200:
        logger.error(f"Failed to fetch data: {response.status_code} {response.text}")
        break

    data = response.json()
    
    # Handle cases where the API returns a dict with a 'data' key or a list directly.
    if isinstance(data, dict):
        items = data.get("data", [])
    elif isinstance(data, list):
        items = data
    else:
        items = []
    
    if not items:
        break

    all_records.extend(items)
    logger.info(f"Retrieved {len(items)} records; total so far: {len(all_records)}")
    
    # Update the offset; break if the number of items returned is less than the limit.
    params["offset"] += len(items)
    if len(items) < params["limit"]:
        break

# Save the complete data to a JSON file.
with open("gamma_data.json", "w") as f:
    json.dump(all_records, f, indent=2)

logger.info(f"Saved {len(all_records)} records to 'gamma_data.json'")
