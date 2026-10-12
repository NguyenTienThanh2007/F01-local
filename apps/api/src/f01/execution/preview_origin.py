"""Opt-in loopback browser origins, isolated per project and never embeddable."""
from urllib.parse import urlsplit
from uuid import UUID

from f01.config import Settings


def browser_origin(settings: Settings, project_id: UUID) -> str | None:
    if not settings.local_browser_preview_enabled:
        return None
    # Recheck the boundary even for nonvalidating model_copy settings.
    preview, factory = urlsplit(settings.preview_origin), urlsplit(settings.factory_origin)
    if not (settings.real_execution_enabled and settings.app_env in ("development", "test")
            and preview.scheme == factory.scheme == "http"
            and preview.hostname == "localhost" and factory.hostname == "127.0.0.1"):
        return None
    port = f":{preview.port}" if preview.port else ""
    return f"http://f01-{project_id.hex}.localhost{port}"
