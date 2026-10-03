import argparse
import json
from pathlib import Path

from f01.main import create_app

parser = argparse.ArgumentParser(
    description="Export the API contract without loading credentials or connecting to a database."
)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
destination = Path(__file__).resolve().parents[3] / "packages/api-client/openapi.json"
content = json.dumps(create_app().openapi(), sort_keys=True, indent=2) + "\n"
if args.check:
    if not destination.exists() or destination.read_text() != content:
        raise SystemExit("OpenAPI drift: run pnpm api:generate.")
    print("OpenAPI contract is current.")
else:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content)
    print("Exported OpenAPI contract.")
