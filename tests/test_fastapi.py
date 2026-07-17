import sys
sys.path.insert(0, 'C:\\SS')

from fastapi.testclient import TestClient
from ui_client.main import app
import traceback

client = TestClient(app)

try:
    response = client.get("/")
    print(f"Status Code: {response.status_code}")
    print(response.text)
except Exception as e:
    print("FATAL ERROR:")
    traceback.print_exc()
