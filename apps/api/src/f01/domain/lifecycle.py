from typing import Literal

Lifecycle = Literal[
    "idle",
    "understanding",
    "planning",
    "building",
    "verifying",
    "deploying",
    "live",
    "error",
]
Phase = Literal["understanding", "planning", "building", "verifying", "deploying"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]
ACTIVE_STATUSES = ("queued", "running")


def transition_status(current: RunStatus, target: RunStatus) -> RunStatus:
    allowed: dict[RunStatus, set[RunStatus]] = {
        "queued": {"running", "failed", "canceled"},
        "running": {"succeeded", "failed", "canceled"},
        "succeeded": set(),
        "failed": set(),
        "canceled": set(),
    }
    if target not in allowed[current]:
        raise ValueError("Invalid run status transition.")
    return target


def transition_phase(
    current: Phase | None, target: Phase, *, repair_event_sequence: int | None = None
) -> Phase:
    next_phase: dict[Phase | None, Phase | None] = {
        None: "understanding",
        "understanding": "planning",
        "planning": "building",
        "building": "verifying",
        "verifying": "deploying",
        "deploying": None,
    }
    repair = (
        current == "verifying"
        and target == "building"
        and repair_event_sequence is not None
        and repair_event_sequence > 0
    )
    if next_phase[current] != target and not repair:
        raise ValueError("Invalid run phase transition.")
    return target


def lifecycle_after_terminal(status: RunStatus, *, has_version: bool) -> Lifecycle:
    if status == "succeeded":
        return "live"
    if status == "failed":
        return "error"
    if status == "canceled":
        return "live" if has_version else "idle"
    raise ValueError("A terminal run is required.")
