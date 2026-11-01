"""Prove that verification guards fail on violations rather than hiding them."""
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def test_provider_network_is_blocked():
    with socket.socket() as connection:
        with pytest.raises(pytest.fail.Exception, match="External network access attempted"):
            connection.connect(("203.0.113.1", 443))


def test_secret_check_rejects_a_staged_credential_without_printing_it(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    credential = "AIza" + "x" * 35
    (tmp_path / "settings.txt").write_text(credential, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "settings.txt"], check=True)
    script = Path(__file__).resolve().parents[2] / "scripts/check_secrets.py"
    result = subprocess.run([sys.executable, str(script), "--root", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "settings.txt" in result.stdout and "Google API key" in result.stdout
    assert credential not in result.stdout + result.stderr
    (tmp_path / "settings.txt").write_text("ordinary configuration", encoding="utf-8")
    result = subprocess.run([sys.executable, str(script), "--root", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0
