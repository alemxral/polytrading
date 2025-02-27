import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level to DEBUG
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from .env file
logger.debug("Environment variables loaded.")

# Define constants for auth levels.
L1 = 1
L2 = 2

# Custom exception for authentication errors.
class PolyException(Exception):
    pass

L1_AUTH_UNAVAILABLE = "Level 1 Authentication not available"
L2_AUTH_UNAVAILABLE = "Level 2 Authentication not available"

# Stub definitions for ApiCreds and Signer (replace with your actual implementations)
class ApiCreds:
    def __init__(self, api_key, api_secret, api_passphrase):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        logger.debug("ApiCreds initialized.")

class Signer:
    def __init__(self, key, chain_id):
        self.key = key
        self.chain_id = chain_id
        logger.debug(f"Signer initialized with key: {key} and chain_id: {chain_id}")

class ClobClient:
    def __init__(
        self,
        host: str = None,
        chain_id: int = None,
        key: str = None,
        creds: ApiCreds = None,
        signature_type: int = None,
        funder: str = None,
    ):
        """
        Initializes the CLOB client.
        Modes:
         - Level 0: Only the host provided.
         - Level 1: Host, chain_id, and key provided.
         - Level 2: Host, chain_id, key, and credentials provided.
        """
        # Set default values from environment variables if not provided.
        host = host or os.getenv("HOST", "https://clob.polymarket.com/")
        chain_id = chain_id if chain_id is not None else int(os.getenv("CHAIN_ID", "137"))
        key = key or os.getenv("POLYGON_KEY")
        signature_type = signature_type if signature_type is not None else int(os.getenv("SIGNATURE_TYPE", "2"))
        funder = funder or os.getenv("FUNDER", "0xF937dBe9976Ac34157b30DD55BDbf248458F6b43")

        logger.debug(f"Initializing ClobClient with host: {host}, chain_id: {chain_id}, key: {key}, signature_type: {signature_type}, funder: {funder}")

        # If credentials are not provided, initialize from environment.
        if creds is None:
            creds = ApiCreds(
                api_key=os.getenv("API_KEY"),
                api_secret=os.getenv("API_SECRET"),
                api_passphrase=os.getenv("API_PASSPHRASE")
            )
            logger.debug("Credentials not provided; using environment defaults.")

        self.host = host.rstrip("/")
        self.chain_id = chain_id
        self.signer = Signer(key, chain_id) if key else None
        self.creds = creds
        self.signature_type = signature_type
        self.funder = funder

        # Determine the client mode.
        self.mode = self._get_client_mode()
        logger.debug(f"Client initialized in mode: {self.mode}")

    def _get_client_mode(self):
        """
        Determine the authentication level of the client.
        Level 0: No authentication.
        Level 1: A signer (private key) is provided.
        Level 2: Both a signer and credentials are provided.
        """
        if self.signer and self.creds:
            return L2
        elif self.signer:
            return L1
        else:
            return 0

    def assert_level_1_auth(self):
        """
        Ensures that the client has Level 1 authentication.
        """
        logger.debug("Asserting level 1 authentication.")
        if self.mode < L1:
            logger.error("Level 1 authentication unavailable.")
            raise PolyException(L1_AUTH_UNAVAILABLE)
        logger.debug("Level 1 authentication is available.")

    def assert_level_2_auth(self):
        """
        Ensures that the client has Level 2 authentication.
        """
        logger.debug("Asserting level 2 authentication.")
        if self.mode < L2:
            logger.error("Level 2 authentication unavailable.")
            raise PolyException(L2_AUTH_UNAVAILABLE)
        logger.debug("Level 2 authentication is available.")

# Module-level function to create and return the default client instance.
def get_default_client():
    logger.debug("Creating default ClobClient instance.")
    client = ClobClient()
    return client

# Create a default client instance that can be imported in other modules.
default_client = get_default_client()

if __name__ == "__main__":
    # For testing purposes, print a simple confirmation that the client was initialized.
    logger.debug("Running module as __main__ for testing.")
    client = get_default_client()
    print("Default ClobClient initialized with host:", client.host)

    # Example usage of the auth assertions:
    try:
        client.assert_level_1_auth()
        print("Level 1 authentication is available.")
    except PolyException as e:
        print("Auth check failed:", e)

    try:
        client.assert_level_2_auth()
        print("Level 2 authentication is available.")
    except PolyException as e:
        print("Auth check failed:", e)
