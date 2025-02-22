import os
import json
import requests
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.exceptions import PolyApiException
from py_clob_client.clob_types import ApiCreds

# Load environment variables from your .env file
load_dotenv()

# Retrieve credentials from the environment
POLYGON_KEY = os.getenv("POLYGON_KEY")
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")

# Define the host URL and Polygon chain ID
host = "https://clob.polymarket.com/"
chain_id = 137  # Polygon's chain ID

# -------------------------------
# Initialize Clients for Each Level
# -------------------------------

# Level 0: Public endpoints only (no authentication)
client_level_0 = ClobClient(host)
print("Level 0 client initialized (public endpoints)")

# Level 1: Requires host, chain_id, and a private key.
client_level_1 = ClobClient(host, chain_id=chain_id, key=POLYGON_KEY)
print("Level 1 client initialized (L1 authentication, private key)")

# Level 2: Requires host, chain_id, private key, and API credentials.
creds = ApiCreds(api_key=API_KEY, api_secret=API_SECRET, api_passphrase=API_PASSPHRASE)
client_level_2 = ClobClient(host, chain_id=chain_id, key=POLYGON_KEY, creds=creds)
print("Level 2 client initialized (L2 authentication, API credentials)")

# -------------------------------
# Function to Check Access Status
# -------------------------------
def check_access_status(client):
    """
    Calls the access status endpoint to check whether a certificate is required.
    Endpoint: GET {host}/auth/ban-status/cert-required?address={signer address}
    This endpoint requires L1 authentication.
    """
    # Build the URL for the access status endpoint
    url = host.rstrip('/') + '/auth/ban-status/cert-required'
    
    # Assume the client stores the authenticated Polygon address (L1) as an attribute.
    # (If not, you may need to derive it from your private key.)
    address = getattr(client, "address", None)
    if not address:
        print("Unable to retrieve the authenticated address from the client.")
        return None

    # Set query parameters
    params = {"address": address}

    # Verify that the client is L1-authenticated
    try:
        client.assert_level_1_auth()
    except PolyApiException as e:
        print("Level 1 authorization check failed:", e)
        return None

    # Attempt to generate L1 headers.
    # This assumes the client has a helper method to build these headers.
    if hasattr(client, "_build_l1_headers"):
        headers = client._build_l1_headers()
    else:
        # If no helper exists, headers must be generated manually.
        # (For brevity, we're leaving this empty. In practice, you'll need the L1 headers:
        # POLY_ADDRESS, POLY_SIGNATURE, POLY_TIMESTAMP, and POLY_NONCE.)
        headers = {}
        print("Warning: L1 headers are not auto-generated; ensure proper signing of the request.")

    print("Checking access status for address:", address)
    
    # Make the GET request using requests (the client library uses similar helpers internally)
    response = requests.get(url, params=params, headers=headers)
    
    try:
        result = response.json()
    except Exception as e:
        print("Failed to decode JSON response:", e)
        result = None
    return result

# -------------------------------
# Check the Access Status using Level 1 Client
# -------------------------------
access_status = check_access_status(client_level_1)
print("Access Status (cert_required):", json.dumps(access_status, indent=4))
