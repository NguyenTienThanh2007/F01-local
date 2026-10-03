"""Operator-only verified ownership linking. Never infer ownership from email."""
import argparse
from pathlib import Path
from uuid import UUID
from f01.application.identity import OIDCVerifier, resolve_identity
from f01.config import get_settings
from f01.db.session import Database
from f01.domain.errors import ApplicationError

def main() -> None:
    parser = argparse.ArgumentParser(description="Link a verified provider subject to an existing development user without changing project/history IDs.")
    parser.add_argument("--user-id", type=UUID, required=True)
    parser.add_argument("--access-token-file", type=Path, required=True, help="Private file containing an unexpired RS256 API access token for the intended owner")
    args = parser.parse_args()
    settings = get_settings()
    if settings.auth_mode != "oidc": raise SystemExit("Configure OIDC before verified ownership linking.")
    token = args.access_token_file.read_text().strip()
    database = Database(settings.database_url)
    try:
        verified = OIDCVerifier(settings).access(token)
        principal = resolve_identity(database, verified, existing_user_id=args.user_id)
        print(f"Linked verified identity to stable internal user {principal.id}. Project/history IDs were preserved.")
    except ApplicationError as exc:
        raise SystemExit(f"Identity linking rejected: {exc.code}. No ownership was reassigned.") from None
    finally: database.close()

if __name__ == "__main__": main()
