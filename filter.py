import pandas as pd
import json
import ast

# File names (adjust if needed)
csv_filename = "markets_all.csv"
tokens_json_filename = "tokens_premier_league.json"
tokens_csv_filename = "tokens_matrix.csv"
paired_tokens_json_filename = "paired_tokens.json"

# Load the CSV data
df = pd.read_csv(csv_filename)

# Define filter criteria
tags_to_filter = {'Soccer', 'Sports', 'EPL', 'Premier League'}

def has_required_tag(tags_value):
    """
    Checks if tags_value contains any of the required tags.
    Handles NaN values, JSON-formatted strings, or lists.
    """
    if pd.isna(tags_value):
        return False
    if isinstance(tags_value, list):
        return any(tag in tags_value for tag in tags_to_filter)
    if not isinstance(tags_value, str):
        return False
    try:
        tags = json.loads(tags_value)
        if isinstance(tags, list):
            return any(tag in tags for tag in tags_to_filter)
    except Exception:
        # Fallback: assume it's a simple string containing comma-separated tags.
        return any(tag in tags_value for tag in tags_to_filter)
    return False

def slug_filter(slug):
    """
    Checks if market_slug indicates a Premier League win event.
    """
    if not isinstance(slug, str):
        return False
    return ("-wins-the-premier-league" in slug) or ("-win-the-premier-league" in slug)

# Filter rows by active status, market_slug, and required tags.
filtered_df = df[
    (df['active'] == True) &
    (df['market_slug'].apply(slug_filter)) &
    (df['tags'].apply(has_required_tag))
]

# Prepare lists to collect token data.
unpaired_tokens_list = []  # All tokens individually (with added fields)
paired_tokens_list = []    # Paired tokens for each market (yes/no)

# Iterate through each filtered row.
for idx, row in filtered_df.iterrows():
    tokens_field = row.get("tokens")
    if pd.isna(tokens_field):
        continue
    try:
        # Try JSON parsing first; if that fails, use ast.literal_eval.
        try:
            tokens = json.loads(tokens_field)
        except Exception:
            tokens = ast.literal_eval(tokens_field)
        if not isinstance(tokens, list):
            continue

        # Add market_slug and question_id to each token.
        for token in tokens:
            token["market_slug"] = row.get("market_slug")
            token["question_id"] = row.get("question_id")

        # Save individual tokens.
        unpaired_tokens_list.extend(tokens)

        # Now, try to pair tokens by outcome ("Yes" and "No").
        token_yes = None
        token_no = None
        for token in tokens:
            outcome = token.get("outcome", "").strip().lower()
            if outcome == "yes":
                token_yes = token
            elif outcome == "no":
                token_no = token

        # If both outcomes are present, create a paired record.
        if token_yes is not None and token_no is not None:
            paired_tokens_list.append({
                "question_id": row.get("question_id"),
                "market_slug": row.get("market_slug"),
                "yes_token": token_yes,
                "no_token": token_no
            })
    except Exception as e:
        print(f"Error parsing tokens in row {idx}: {e}")

# Save unpaired tokens as a CSV and JSON.
tokens_df = pd.DataFrame(unpaired_tokens_list)
tokens_df.to_csv(tokens_csv_filename, index=False)
with open(tokens_json_filename, "w") as f:
    json.dump(unpaired_tokens_list, f, indent=2)

# Save the paired tokens to a separate JSON file.
with open(paired_tokens_json_filename, "w") as f:
    json.dump(paired_tokens_list, f, indent=2)

print(f"Extracted {len(unpaired_tokens_list)} token records individually.")
print(f"Extracted {len(paired_tokens_list)} paired token records.")
print(f"Tokens CSV saved to '{tokens_csv_filename}', unpaired tokens JSON saved to '{tokens_json_filename}',")
print(f"and paired tokens JSON saved to '{paired_tokens_json_filename}'.")
