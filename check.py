import json
import os

# File names (adjust if needed)
TOKEN_FILE = "tokens_premier_league.json"
RESPONSE_SAMPLE_FILE = "response_sample.json"

def load_requested_tokens():
    """
    Load token IDs from TOKEN_FILE. If the file is missing or empty,
    use a fallback token ID.
    Assumes the file contains a list of dicts with a 'token_id' field.
    """
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                tokens = json.load(f)
            token_ids = [token.get("token_id") for token in tokens if token.get("token_id")]
            if token_ids:
                return token_ids
            else:
                print("Token file exists but no token IDs found; using fallback.")
        except Exception as e:
            print(f"Error loading tokens from file: {e}")
    # Fallback token list if file doesn't exist or loading fails.
    fallback_token = "6458391015326318827030964562167292825976142887663920584763082996854768753111"
    return [fallback_token]

def extract_asset_ids(data):
    """
    Recursively extract any string values found under the key 'asset_id'
    from the given JSON object.
    """
    asset_ids = set()
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "asset_id" and isinstance(value, str):
                asset_ids.add(value)
            else:
                asset_ids.update(extract_asset_ids(value))
    elif isinstance(data, list):
        for item in data:
            asset_ids.update(extract_asset_ids(item))
    return asset_ids

def main():
    # Load requested tokens.
    requested_tokens = load_requested_tokens()
    print("Requested token IDs:")
    print(requested_tokens)
    
    # Load the saved JSON response.
    if not os.path.exists(RESPONSE_SAMPLE_FILE):
        print(f"Response file '{RESPONSE_SAMPLE_FILE}' not found.")
        return

    try:
        with open(RESPONSE_SAMPLE_FILE, "r") as f:
            response_data = json.load(f)
    except Exception as e:
        print(f"Error loading response file: {e}")
        return

    # Extract asset_ids from the response.
    received_token_ids = extract_asset_ids(response_data)
    print("\nReceived token IDs in response:")
    print(list(received_token_ids))
    
    # Check which requested tokens are missing in the response.
    missing = set(requested_tokens) - received_token_ids
    if missing:
        print("\nMissing token IDs in response:")
        print(list(missing))
    else:
        print("\nAll requested tokens were found in the response.")

if __name__ == "__main__":
    main()
