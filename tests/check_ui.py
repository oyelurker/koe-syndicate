import urllib.request
try:
    req = urllib.request.urlopen("http://127.0.0.1:8000/")
    if req.getcode() == 200:
        print("UI Client is online.")
except Exception as e:
    print(f"Waiting for UI Client: {e}")
