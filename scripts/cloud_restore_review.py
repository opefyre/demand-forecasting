"""Verify a downloaded cloud backup in a new, paused review workspace only."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cloud_state import restore_for_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--company', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    receipt = restore_for_review(args.source, args.destination, args.company, args.sha256)
    print(json.dumps({key: receipt[key] for key in ['archive_sha256', 'verified_files', 'changes']}, indent=2))


if __name__ == '__main__':
    main()
