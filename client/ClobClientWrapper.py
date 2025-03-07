import os
import logging
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# Load environment variables (ensure your .env file is in .gitignore)
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

class ClobClientWrapper(ClobClient):
    """
    A wrapper for ClobClient that inherits all methods and properties.
    This wrapper provides additional convenience methods such as print_auth_info.
    """
    def __init__(self,
                 host: str,
                 chain_id: int,
                 key: str,
                 creds: ApiCreds,
                 signature_type: int,
                 funder: str):
        super().__init__(
            host=host,
            chain_id=chain_id,
            key=key,
            creds=creds,
            signature_type=signature_type,
            funder=funder
        )
        # Explicitly store signature_type in case parent doesn't set it.
        self.signature_type = signature_type

    def print_auth_info(self):
        auth_level = getattr(self, "mode", 0)
        if auth_level == 0:
            level_str = "Level 0 (No Authentication)"
        elif auth_level == 1:
            level_str = "Level 1 (Signer Provided)"
        elif auth_level == 2:
            level_str = "Level 2 (Signer and Credentials Provided)"
        else:
            level_str = "Unknown Authentication Level"
        logger.info(f"Client Authentication Level: {level_str}")
        print(f"Client Authentication Level: {level_str}")
        return level_str

    def get_client_info(self):
        info = {
            "host": self.host,
            "chain_id": self.chain_id,
            "signature_type": self.signature_type,
            "funder": self.funder,
            "auth_level": self.print_auth_info()
        }
        return info

def create_default_clob_client_wrapper():
    """
    Factory function that creates a ClobClientWrapper using values loaded from environment variables.
    Ensure that the .env file (or environment) contains the required keys.
    """
    # These variables should be set in your environment/.env file.
    host = os.getenv("HOST")
    chain_id = int(os.getenv("CHAIN_ID"))
    key = os.getenv("POLYGON_KEY")
    signature_type = int(os.getenv("SIGNATURE_TYPE"))
    funder = os.getenv("FUNDER")
    
    creds = ApiCreds(
        api_key=os.getenv("API_KEY"),
        api_secret=os.getenv("API_SECRET"),
        api_passphrase=os.getenv("API_PASSPHRASE")
    )
    
    logger.debug("Creating ClobClientWrapper with environment configuration.")
    
    client = ClobClientWrapper(
        host=host,
        chain_id=chain_id,
        key=key,
        creds=creds,
        signature_type=signature_type,
        funder=funder
    )
    return client

if __name__ == "__main__":
    wrapper = create_default_clob_client_wrapper()
    print("Default ClobClientWrapper initialized with host:", wrapper.host)
    wrapper.print_auth_info()
    print("Client Info:", wrapper.get_client_info())
