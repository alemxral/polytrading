import pandas as pd
import json
import ast
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EvenTracker")

class EvenTracker:
    def __init__(self,
                 csv_filename="markets_all.csv",
                 tokens_json_filename="tokens_premier_league.json",
                 tokens_csv_filename="tokens_matrix.csv",
                 paired_tokens_json_filename="paired_tokens.json",
                 tags_to_filter=None):
        """
        Initializes the EvenTracker with file names and filter criteria.
        Loads the events data from the given CSV file.
        """
        self.csv_filename = csv_filename
        self.tokens_json_filename = tokens_json_filename
        self.tokens_csv_filename = tokens_csv_filename
        self.paired_tokens_json_filename = paired_tokens_json_filename
        self.tags_to_filter = tags_to_filter or {'Soccer', 'Sports', 'EPL', 'Premier League'}
        
        try:
            self.df = pd.read_csv(self.csv_filename)
            logger.info(f"Loaded {len(self.df)} records from {self.csv_filename}.")
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}")
            self.df = pd.DataFrame()
        
        self.filtered_df = None
        self.unpaired_tokens_list = []  # Individual tokens (with added market_slug, question_id)
        self.paired_tokens_list = []    # Paired tokens for each event (yes and no)
    
    def has_required_tag(self, tags_value):
        """
        Returns True if tags_value (which can be NaN, a JSON string, or list) contains any required tag.
        """
        if pd.isna(tags_value):
            return False
        if isinstance(tags_value, list):
            return any(tag in tags_value for tag in self.tags_to_filter)
        if not isinstance(tags_value, str):
            return False
        try:
            tags = json.loads(tags_value)
            if isinstance(tags, list):
                return any(tag in tags for tag in self.tags_to_filter)
        except Exception:
            # Fallback: check the string directly (e.g. comma-separated values)
            return any(tag in tags_value for tag in self.tags_to_filter)
        return False
    
    @staticmethod
    def slug_filter(slug):
        """
        Returns True if the market_slug indicates a Premier League win event.
        """
        if not isinstance(slug, str):
            return False
        return ("-wins-the-premier-league" in slug) or ("-win-the-premier-league" in slug)
    
    def filter_events(self):
        """
        Filters the loaded CSV data to keep only:
          - rows with active == True,
          - rows whose market_slug passes slug_filter,
          - rows whose tags contain at least one of the required tags.
        Stores the result in self.filtered_df.
        """
        if self.df.empty:
            logger.warning("No data loaded; cannot filter events.")
            self.filtered_df = self.df
            return self.filtered_df
        
        self.filtered_df = self.df[
            (self.df['active'] == True) &
            (self.df['market_slug'].apply(self.slug_filter)) &
            (self.df['tags'].apply(self.has_required_tag))
        ]
        logger.info(f"Filtered events: {len(self.filtered_df)} records remain.")
        return self.filtered_df

    def process_tokens(self):
        """
        Iterates over each row in the filtered data and processes the 'tokens' field.
        For each row:
          - Attempts to parse the tokens field (first as JSON, then with ast.literal_eval).
          - Adds the 'market_slug' and 'question_id' from the row to each token.
          - Appends all tokens to self.unpaired_tokens_list.
          - Attempts to pair tokens: one with outcome "yes" and one with outcome "no".
            If both are present, adds a record to self.paired_tokens_list.
        """
        if self.filtered_df is None:
            self.filter_events()
        
        for idx, row in self.filtered_df.iterrows():
            tokens_field = row.get("tokens")
            if pd.isna(tokens_field):
                continue
            try:
                try:
                    tokens = json.loads(tokens_field)
                except Exception:
                    tokens = ast.literal_eval(tokens_field)
                if not isinstance(tokens, list):
                    continue
                
                # Add extra fields to each token.
                for token in tokens:
                    token["market_slug"] = row.get("market_slug")
                    token["question_id"] = row.get("question_id")
                # Save individual tokens.
                self.unpaired_tokens_list.extend(tokens)
                
                # Attempt to pair tokens by outcome.
                token_yes = None
                token_no = None
                for token in tokens:
                    outcome = token.get("outcome", "").strip().lower()
                    if outcome == "yes":
                        token_yes = token
                    elif outcome == "no":
                        token_no = token
                if token_yes is not None and token_no is not None:
                    self.paired_tokens_list.append({
                        "question_id": row.get("question_id"),
                        "market_slug": row.get("market_slug"),
                        "yes_token": token_yes,
                        "no_token": token_no
                    })
            except Exception as e:
                logger.error(f"Error parsing tokens in row {idx}: {e}")
        
        logger.info(f"Extracted {len(self.unpaired_tokens_list)} token records individually.")
        logger.info(f"Extracted {len(self.paired_tokens_list)} paired token records.")

    def save_results(self):
        """
        Saves the unpaired tokens to CSV and JSON, and the paired tokens to a separate JSON file.
        """
        # Save unpaired tokens as CSV.
        try:
            tokens_df = pd.DataFrame(self.unpaired_tokens_list)
            tokens_df.to_csv(self.tokens_csv_filename, index=False)
            logger.info(f"Unpaired tokens CSV saved to '{self.tokens_csv_filename}'.")
        except Exception as e:
            logger.error(f"Error saving tokens CSV: {e}")
        # Save unpaired tokens as JSON.
        try:
            with open(self.tokens_json_filename, "w") as f:
                json.dump(self.unpaired_tokens_list, f, indent=2)
            logger.info(f"Unpaired tokens JSON saved to '{self.tokens_json_filename}'.")
        except Exception as e:
            logger.error(f"Error saving unpaired tokens JSON: {e}")
        # Save paired tokens as JSON.
        try:
            with open(self.paired_tokens_json_filename, "w") as f:
                json.dump(self.paired_tokens_list, f, indent=2)
            logger.info(f"Paired tokens JSON saved to '{self.paired_tokens_json_filename}'.")
        except Exception as e:
            logger.error(f"Error saving paired tokens JSON: {e}")
    
    def run(self):
        """
        Executes the complete pipeline:
          - Filter events,
          - Process tokens,
          - Save the results.
        Prints a summary of extraction.
        """
        self.filter_events()
        self.process_tokens()
        self.save_results()
        print(f"Extracted {len(self.unpaired_tokens_list)} token records individually.")
        print(f"Extracted {len(self.paired_tokens_list)} paired token records.")
        print(f"Tokens CSV saved to '{self.tokens_csv_filename}', unpaired tokens JSON saved to '{self.tokens_json_filename}',")
        print(f"and paired tokens JSON saved to '{self.paired_tokens_json_filename}'.")


# --- Example Usage ---
if __name__ == "__main__":
    tracker = EvenTracker()
    tracker.run()
