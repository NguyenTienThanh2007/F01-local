"""Create local environment files without overwriting existing values."""

from pathlib import Path
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]


def create_private_file(path: Path, text: str) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f"Kept existing {path.relative_to(ROOT)}")
        return
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(text)
    print(f"Created {path.relative_to(ROOT)}")


if __name__ == "__main__":
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    template = template.replace("DEV_API_TOKEN=\n", f"DEV_API_TOKEN={secrets.token_urlsafe(32)}\n")
    create_private_file(ROOT / ".env", template)
    create_private_file(ROOT / "apps/api/.env", "OPENAI_API_KEY=\n")
    print("Local environment ready. Values were not displayed.")
