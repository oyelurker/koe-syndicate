import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lead_finder.lead_finder.tools.maps_search import google_maps_search

print('Searching with exclude_websites=True...')
res1 = google_maps_search('New Delhi', exclude_websites=True)
print(f"Result count: {res1.get('total_results', 0)}")

print('Searching with exclude_websites=False...')
res2 = google_maps_search('New Delhi', exclude_websites=False)
print(f"Result count: {res2.get('total_results', 0)}")
