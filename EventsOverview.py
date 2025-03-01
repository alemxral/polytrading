import os
import logging
import json
import pandas as pd
import requests
from dotenv import load_dotenv
from ClobClientWrapper import default_client

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EventsOverview")

# Load environment variables (if needed)
load_dotenv()

class EventsOverview:
    def __init__(self):
        """
        Initializes the EventsOverview instance.
        Sets the Polymarket client and builds the events endpoint.
        The fetched events will be stored in self.events (a list).
        """
        self.client = default_client  # Pre-initialized client from your initialize_client module
        # Assuming the hosted endpoint for markets is at /markets relative to client.host
        self.endpoint = f"{self.client.host}/markets"
        self.events = []  # Will store the fetched events data

    def fetch_events(self):
        """
        Fetches events (market data) from Polymarket using the hosted endpoint.
        Paginates through the results until no more events are found.
        """
        all_events = []
        next_cursor = ""  # Start with an empty cursor
        
        while True:
            params = {}
            if next_cursor:
                params["next_cursor"] = next_cursor

            logger.info(f"Fetching markets with next_cursor: '{next_cursor}'")
            try:
                response = requests.get(self.endpoint, params=params)
            except Exception as e:
                logger.error(f"Request error: {e}")
                break

            if response.status_code != 200:
                logger.error(f"Failed to fetch markets: {response.status_code} {response.text}")
                break

            data = response.json()

            # Data can be either a dict with 'data' and 'next_cursor' or a list
            if isinstance(data, dict):
                events = data.get("data", [])
                next_cursor = data.get("next_cursor", "")
            elif isinstance(data, list):
                events = data
                next_cursor = ""
            else:
                logger.error("Unexpected data format received.")
                break

            if not events:
                logger.info("No more events found.")
                break

            all_events.extend(events)

            # Stop if there's no cursor or if it indicates the end (e.g., "LTE=")
            if not next_cursor or next_cursor == "LTE=":
                break

        self.events = all_events
        logger.info(f"Total events retrieved: {len(self.events)}")
        return self.events

    def save_to_json(self, filename="markets_all.json"):
        """
        Saves the fetched events to a JSON file.
        """
        if not self.events:
            logger.warning("No events data to save.")
            return
        try:
            with open(filename, "w") as f:
                json.dump(self.events, f, indent=2)
            logger.info(f"Saved events to JSON file: {filename}")
        except Exception as e:
            logger.error(f"Error saving JSON: {e}")

    def save_to_csv(self, filename="markets_all.csv"):
        """
        Saves the fetched events to a CSV file.
        Converts the events list to a pandas DataFrame.
        """
        if not self.events:
            logger.warning("No events data to save.")
            return
        try:
            df = pd.DataFrame(self.events)
            # Ensure that there is a timestamp column in the CSV.
            if "timestamp" not in df.columns:
                df["timestamp"] = ""
            df.to_csv(filename, index=False)
            logger.info(f"CSV file '{filename}' created successfully with {len(self.events)} records.")
        except Exception as e:
            logger.error(f"Error saving CSV: {e}")

    def get_headers(self):
        """
        Returns a header vector (list) based on the keys of the first event.
        If no events are present, returns an empty list.
        """
        if not self.events:
            logger.warning("No events data available to extract headers.")
            return []
        # Use the first event to derive headers. You can add additional headers if needed.
        headers = list(self.events[0].keys())
        if "timestamp" not in headers:
            headers.append("timestamp")
        return headers

    def filter_events(self, **criteria):
        """
        Filters the events based on provided criteria.
        Example usage: filter_events(active=True, market_slug="will-man-city-win-the-premier-league")
        Returns a list of events matching all the criteria.
        """
        if not self.events:
            logger.warning("No events data available to filter.")
            return []
        filtered = []
        for event in self.events:
            match = True
            for key, value in criteria.items():
                # Use lower-case comparison for strings if needed
                if key in event:
                    event_value = event[key]
                    if isinstance(event_value, str) and isinstance(value, str):
                        if event_value.lower() != value.lower():
                            match = False
                            break
                    else:
                        if event_value != value:
                            match = False
                            break
                else:
                    match = False
                    break
            if match:
                filtered.append(event)
        logger.info(f"Filtered events count: {len(filtered)}")
        return filtered

# --- Example usage ---
if __name__ == "__main__":
    eo = EventsOverview()
    eo.fetch_events()
    # Save the complete data to JSON and CSV
    eo.save_to_json("EventsOverview.json")
    eo.save_to_csv("EventsOverview.csv")
    
    # Print headers vector
    headers = eo.get_headers()
    logger.info(f"Headers: {headers}")
    
    # Example filtering: get only active events (if there is an 'active' field)
    filtered = eo.filter_events(active=True)
    if filtered:
        logger.info("Filtered events sample:")
        # Print first 3 filtered events for example.
        for event in filtered[:3]:
            print(json.dumps(event, indent=2))
    else:
        logger.info("No events match the filter criteria.")
