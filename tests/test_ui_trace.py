import subprocess
import time
import urllib.request
import sys

print("Starting UI Client...")
process = subprocess.Popen(
    ["C:\\SS\\venv\\Scripts\\python.exe", "-m", "ui_client"],
    cwd="C:\\SS",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)

time.sleep(3)

print("Sending request to http://127.0.0.1:8000/")
try:
    urllib.request.urlopen("http://127.0.0.1:8000/")
    print("Request successful!")
except Exception as e:
    print(f"Request failed: {e}")

print("Terminating UI Client...")
process.terminate()
time.sleep(1)

print("UI Client Output:")
out, err = process.communicate()
print(out.decode('utf-8'))
