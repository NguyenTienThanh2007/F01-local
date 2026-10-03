"""Legacy database-free development planner limits; OIDC uses the durable ledger."""
from datetime import UTC, datetime, timedelta
from threading import Lock
from f01.config import Settings
from f01.domain.errors import ApplicationError

class DevelopmentBudget:
    def __init__(self) -> None:
        self.lock = Lock()
        self.requests: list[tuple[datetime, int]] = []
        self.active = False

    def reserve(self, settings: Settings, tokens: int) -> None:
        now = datetime.now(UTC)
        with self.lock:
            self.requests = [(when, used) for when, used in self.requests if when.date() == now.date()]
            if self.active: raise ApplicationError("PLANNING_IN_PROGRESS")
            if len(self.requests) >= settings.planning_requests_per_day or sum(when >= now-timedelta(minutes=1) for when, _ in self.requests) >= settings.planning_requests_per_minute:
                raise ApplicationError("PLANNING_RATE_LIMITED")
            if tokens + sum(used for _, used in self.requests) > settings.planning_daily_token_budget:
                raise ApplicationError("PLANNING_BUDGET_EXCEEDED")
            self.requests.append((now, tokens)); self.active = True

    def release(self) -> None:
        with self.lock: self.active = False
