"""Read a supervisor snapshot without claiming death or replaying work."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.run_tests import supervision_status
except ModuleNotFoundError:
    from run_tests import supervision_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", type=Path, help="supervision resource.json snapshot")
    args = parser.parse_args()
    print(json.dumps(supervision_status(args.resource)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
