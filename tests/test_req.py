import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8000/")
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
