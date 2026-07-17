import urllib.request
import urllib.error

try:
    urllib.request.urlopen("http://127.0.0.1:8000/")
    print("SUCCESS")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode('utf-8', errors='replace'))
except Exception as e:
    print(f"Other Error: {e}")
