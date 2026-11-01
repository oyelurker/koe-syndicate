"""Import every service entrypoint without allowing outbound network connections."""
import importlib
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
original_connect = socket.socket.connect


def offline_connect(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError("Outbound network access is prohibited in import smoke checks")
    return original_connect(sock, address)


with patch.object(socket.socket, "connect", offline_connect):
    for name in (
        "ui_client.main",
        "lead_finder.__main__",
        "lead_manager.adk_main",
        "sdr.__main__",
        "gmail_pubsub_listener.gmail_listener_service",
    ):
        module = importlib.import_module(name)
        if name == "sdr.__main__":
            assert module.ADK_AVAILABLE, "SDR dependency imports failed"
            assert len(module.app.app.routes) > 1, "SDR fell back to its error application"
        print("PASS", name, flush=True)
