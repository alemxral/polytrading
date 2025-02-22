import requests
import pandas as pd
from py_clob_client.endpoints import GET_ORDER_BOOK
from py_clob_client.client import ClobClient
from py_clob_client.exceptions import PolyApiException
from dotenv import load_dotenv
import os
import json
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds



# Load environment variables from .env
load_dotenv()
# Correctly load the Polygon private key from the environment variable "POLYGON_KEY"
POLYGON_KEY = os.getenv("POLYGON_KEY")


host = "https://clob.polymarket.com/"
chain_id = 137  # Polygon's ChainID



# Create an ApiCreds object with your L2 credentials
api_creds = ApiCreds(
    api_key="07c6cd54-44d3-8b4c-2813-d8381aab547b",
    api_secret="03dwZX1mUeIX-T13z4UAYwf2a_Kd8fTfR_Tu3KwDCCw=",
    api_passphrase="5e9901203477fd407d8f11121fb079a884a49d74158301763c2cc9b30b6c440c"
)

# Instantiate the client with the API credentials
client = ClobClient(
    host=host,
    chain_id=137,
    key=POLYGON_KEY,  # your signing key
    creds=api_creds,          # providing your L2 credentials here
    signature_type=2, 
    funder="0xF937dBe9976Ac34157b30DD55BDbf248458F6b43"
)

MSG=client.derive_api_key()

# Now you can call methods that require L2 authentication, e.g., get_order:
order = client.get_order("0x9f85eca66749070a71196fafda8222dfac9d13287b82a8d050d55f6f38864103")
print(order)
print(MSG)
