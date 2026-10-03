"""At-least-once replay from committed events; no in-memory event authority."""
import asyncio
import re
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime
from hmac import compare_digest
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from f01.application.projects import read_events
from f01.config import Settings
from f01.db.session import Database
from f01.domain.errors import ApplicationError


def credentials_valid(settings: Settings, token: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return settings.auth_mode == "development" and compare_digest(token.encode(), settings.dev_api_token.get_secret_value().encode()) and (
        settings.dev_token_expires_at is None or now < settings.dev_token_expires_at)


def replay_cursor(after_sequence: str | None, last_event_id: str | None) -> int:
    value = last_event_id if last_event_id is not None else after_sequence or "0"
    if len(value) > 10 or not re.fullmatch(r"[0-9]+", value) or int(value) > 2147483647:
        raise ApplicationError("VALIDATION_ERROR")
    return int(value)


async def stream_events(database: Database, owner: UUID, project_id: UUID, cursor: int, settings: Settings, token: str,
    disconnected: Callable[[], Awaitable[bool]], *, poll_seconds: float = .25, heartbeat_seconds: float = 15, authorized: Callable[[], bool] | None = None) -> AsyncGenerator[str, None]:
    async def valid() -> bool:
        return await asyncio.to_thread(authorized) if authorized else credentials_valid(settings, token)
    heartbeat = time.monotonic()
    while not await disconnected():
        if not await valid():
            yield 'event: session_expired\ndata: {"code":"AUTHENTICATION_REQUIRED"}\n\n'
            return
        try:
            page = await asyncio.to_thread(read_events, database, owner, project_id, cursor, 100)
        except ApplicationError:
            yield 'event: access_revoked\ndata: {"code":"NOT_FOUND"}\n\n'
            return
        except SQLAlchemyError:
            return  # close transport; client reconnects/polls, without invented Trace entries
        # Authorization may expire while the database query is in flight.
        if not await valid():
            yield 'event: session_expired\ndata: {"code":"AUTHENTICATION_REQUIRED"}\n\n'
            return
        for event in page.items:
            if not await valid():
                yield 'event: session_expired\ndata: {"code":"AUTHENTICATION_REQUIRED"}\n\n'
                return
            if await disconnected():
                return
            yield f"event: build_event\nid: {event.sequence}\ndata: {event.model_dump_json()}\n\n"
            cursor = event.sequence
        if time.monotonic() - heartbeat >= heartbeat_seconds:
            yield ": heartbeat\n\n"
            heartbeat = time.monotonic()
        if page.next_cursor is None:
            await asyncio.sleep(poll_seconds)
