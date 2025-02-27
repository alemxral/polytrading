import requests
import pandas as pd
from pandas import json_normalize

url = 'https://clob.polymarket.com/markets'
response = requests.get(url)
data = response.json().get("data", [])

# Normalize the top-level market fields and flatten the 'tokens' nested list.
markets_flat = json_normalize(
    data, 
    record_path=['tokens'], 
    meta=['question', 'market_slug'],  # Include other relevant top-level fields
    errors='ignore'
)

markets_flat.to_csv("flattened_markets.csv", index=False)
print("Flattened CSV created.")
