import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# Load environment variables from a .env file once
load_dotenv()

class ClobClientFactory:
    def __init__(self):
        # Read configuration values from environment variables
        self.host = os.getenv("CLOB_HOST", "https://clob.polymarket.com/")
        self.chain_id = int(os.getenv("CHAIN_ID", "137"))
        self.polygon_key = os.getenv("POLYGON_KEY")
        self.api_key = os.getenv("API_KEY", "your_default_api_key")
        self.api_secret = os.getenv("API_SECRET", "your_default_api_secret")
        self.api_passphrase = os.getenv("API_PASSPHRASE", "your_default_api_passphrase")
        self.signature_type = int(os.getenv("SIGNATURE_TYPE", "2"))
        self.funder = os.getenv("FUNDER", "0xF937dBe9976Ac34157b30DD55BDbf248458F6b43")
    
    def create_client(self) -> ClobClient:
        # Create an ApiCreds instance using the loaded configuration
        api_creds = ApiCreds(
            api_key=self.api_key,
            api_secret=self.api_secret,
            api_passphrase=self.api_passphrase
        )
        # Instantiate and return the ClobClient
        return ClobClient(
            host=self.host,
            chain_id=self.chain_id,
            key=self.polygon_key,
            creds=api_creds,
            signature_type=self.signature_type,
            funder=self.funder
        )

# Usage example:
if __name__ == "__main__":
    # Instantiate the factory
    factory = ClobClientFactory()
    # Create the client instance
    client = factory.create_client()
    
    # Optionally derive an API key message if needed
    msg = client.derive_api_key()
    
    # Now use the client to fetch an order
    order = client.get_order("0x9f85eca66749070a71196fafda8222dfac9d13287b82a8d050d55f6f38864103")
    
    print("Order:", order)
    print("Derived API Key Message:", msg)
