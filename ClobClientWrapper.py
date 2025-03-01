import os
import logging
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from .env file
logger.debug("Environment variables loaded.")

class ClobClientWrapper:
    def __init__(self,
                 host: str = None,
                 chain_id: int = None,
                 key: str = None,
                 creds: ApiCreds = None,
                 signature_type: int = None,
                 funder: str = None):
        """
        Initializes the ClobClientWrapper using the ClobClient from py_clob_client.
        Default values are taken from environment variables.
        """
        host = host or os.getenv("HOST", "https://clob.polymarket.com/")
        chain_id = chain_id if chain_id is not None else int(os.getenv("CHAIN_ID", "137"))
        key = key or os.getenv("POLYGON_KEY")
        signature_type = signature_type if signature_type is not None else int(os.getenv("SIGNATURE_TYPE", "2"))
        funder = funder or os.getenv("FUNDER", "0xF937dBe9976Ac34157b30DD55BDbf248458F6b43")
        
        if creds is None:
            creds = ApiCreds(
                api_key=os.getenv("API_KEY"),
                api_secret=os.getenv("API_SECRET"),
                api_passphrase=os.getenv("API_PASSPHRASE")
            )
            logger.debug("Credentials not provided; using environment defaults.")
        
        # Initialize the existing ClobClient
        self.client = ClobClient(
            host=host,
            chain_id=chain_id,
            key=key,
            creds=creds,
            signature_type=signature_type,
            funder=funder
        )
        logger.debug(f"ClobClientWrapper: Initialized ClobClient with host: {self.client.host}")

    def get_auth_level(self):
        """
        Returns the numeric authentication level (0, 1, or 2)
        as determined by the underlying ClobClient (via its 'mode' attribute).
        """
        return getattr(self.client, "mode", 0)

    def get_auth_level_str(self):
        """
        Returns a human-readable description of the authentication level.
        """
        level = self.get_auth_level()
        if level == 0:
            return "Level 0 (No Authentication)"
        elif level == 1:
            return "Level 1 (Signer Provided)"
        elif level == 2:
            return "Level 2 (Signer and Credentials Provided)"
        else:
            return "Unknown Authentication Level"

    def is_authenticated(self):
        """
        Returns True if the client has at least Level 1 authentication.
        """
        return self.get_auth_level() >= 1

    def print_auth_info(self):
        """
        Logs and prints the current authentication status.
        """
        auth_str = self.get_auth_level_str()
        logger.info(f"Client Authentication Level: {auth_str}")
        print(f"Client Authentication Level: {auth_str}")
        return auth_str

    def get_client_info(self):
        """
        Returns a dictionary with key client configuration details.
        """
        info = {
            "host": self.client.host,
            "chain_id": self.client.chain_id,
            "signature_type": self.client.signature_type,
            "funder": self.client.funder,
            "auth_level": self.get_auth_level_str()
        }
        return info

def get_default_client_wrapper():
    logger.debug("Creating default ClobClientWrapper instance.")
    return ClobClientWrapper()

if __name__ == "__main__":
    wrapper = get_default_client_wrapper()
    print("Default ClobClientWrapper initialized with host:", wrapper.client.host)
    wrapper.print_auth_info()
    print("Client Info:", wrapper.get_client_info())
