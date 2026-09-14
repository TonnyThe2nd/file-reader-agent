"""Preview: python -m scripts.retention; apply configured rules with --apply."""
import argparse
import json

from app.core.database import SessionLocal
from app.services.retention_service import apply_retention


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        print(json.dumps(apply_retention(db, dry_run=not args.apply)))


if __name__ == "__main__":
    main()
