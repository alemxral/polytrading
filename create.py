from dotenv import load_dotenv
import os
import json
from py_clob_client.client import ClobClient
from py_clob_client.exceptions import PolyApiException

# Load environment variables from .env
load_dotenv()
POLIGON_KEY = os.getenv("API_KEY")
print("Loaded private key:", PRIVATE_KEY)

host = "https://clob.polymarket.com/"
chain_id = 137  # Polygon's ChainID

client = ClobClient(host, key=POLIGON_KEY, chain_id=chain_id)

try:
    # Derive API credentials
    creds = client.derive_api_key()
    print("Derived API credentials:", creds)

    # Convert the ApiCreds object to a dictionary
    creds_dict = {
        "api_key": creds.api_key,
        "api_secret": creds.api_secret,
        "api_passphrase": creds.api_passphrase,
    }

    # Save the dictionary as a JSON file
    with open("credentials.json", "w") as f:
        json.dump(creds_dict, f, indent=4)

    print("Credentials saved to credentials.json")
except PolyApiException as e:
    print("API Exception occurred:", e)
except Exception as ex:
    print("An unexpected error occurred:", ex)
