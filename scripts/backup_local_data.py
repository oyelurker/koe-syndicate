"""Create or restore a consistent SQLite copy without overwriting existing data."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from ui_client import db
from ui_client.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=db.DB_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/backups" /
                        ("koe-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".db"))
    args = parser.parse_args()
    if args.output.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        parser.error("Use a database suffix so Git excludes the credential-bearing backup")
    Store(args.source).backup(args.output)
    print("Verified database copy:", args.output.resolve())
    print("The token encryption key is not included; preserve it separately.")


if __name__ == "__main__":
    main()
