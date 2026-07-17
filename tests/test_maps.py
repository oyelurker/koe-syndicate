import sys
import os
sys.path.insert(0, 'C:\\SS\\lead_finder')

from dotenv import load_dotenv
load_dotenv('C:\\SS\\.env')

from lead_finder.tools.maps_search import GoogleMapsClient

client = GoogleMapsClient()
print("Searching Delhi...")
results = client.search_businesses("Delhi", max_results=10)
print(f"Found {len(results)} businesses without websites.")
print("Searching Delhi with exclude_websites=False...")
results = client.search_businesses("Delhi", exclude_websites=False, max_results=10)
print(f"Found {len(results)} total businesses.")
