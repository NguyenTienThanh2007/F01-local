from dataclasses import dataclass
from typing import Literal

from f01.domain.lifecycle import Phase


@dataclass(frozen=True)
class FixtureEvent:
    type: str
    message: str
    severity: Literal["info", "warning", "error"] = "info"
    issue: str | None = None
    resolves: str | None = None
    recoverable: bool | None = None


@dataclass(frozen=True)
class Step:
    phase: Phase
    events: tuple[FixtureEvent, ...]
    outcome: Literal["success", "failure"] | None = None
    repair: bool = False


@dataclass(frozen=True)
class Scenario:
    id: str
    version: int
    steps: tuple[Step, ...]


UNDERSTANDING = Step("understanding", (FixtureEvent("step.completed", "Simulation: preserved the saved request and frozen Brain/version context."),))
PLANNING = Step("planning", (FixtureEvent("step.completed", "Simulation: selected a deterministic fixture plan; no model or source generation."),))
BUILDING = Step("building", (FixtureEvent("step.completed", "Simulation: selected a bundled synthetic interface; no files or commits were created."),))
VERIFYING = Step("verifying", (FixtureEvent("verification.passed", "Simulation: fixture verification outcome passed. No application tests were executed."),))
DEPLOYING = Step("deploying", (FixtureEvent("step.completed", "Simulation: preparing an internal fixture record; no external deployment."),))
SUCCESS = Step("deploying", (FixtureEvent("step.completed", "Simulation: fixture demonstration completed; the preview is a curated sample."),), outcome="success")
ISSUE = Step("verifying", (FixtureEvent("verification.failed", "Simulation: sample callback route mismatch selected by the fixture.", "warning", issue="sample-auth-callback", recoverable=True),))
REPAIR = Step("building", (FixtureEvent("repair.recorded", "Simulation: fixture repair relationship recorded; no source fix was performed.", resolves="sample-auth-callback"),), repair=True)
FAILURE_ISSUE = Step("verifying", (FixtureEvent("verification.failed", "Simulation: terminal sample verification failure selected by the fixture.", "error", issue="sample-update-failure", recoverable=False),))
FAILURE = Step("verifying", (), outcome="failure")

# Published scenario definitions are immutable. New fixture behavior needs a new version.
SCENARIOS: dict[tuple[str, int], Scenario] = {
    (name, 1): Scenario(name, 1, steps)
    for name, steps in {
        "crm-success": (UNDERSTANDING, PLANNING, BUILDING, VERIFYING, DEPLOYING, SUCCESS),
        "generic-success": (UNDERSTANDING, PLANNING, BUILDING, VERIFYING, DEPLOYING, SUCCESS),
        "recoverable-verification": (UNDERSTANDING, PLANNING, BUILDING, ISSUE, REPAIR, VERIFYING, DEPLOYING, SUCCESS),
        "terminal-failure": (UNDERSTANDING, PLANNING, BUILDING, FAILURE_ISSUE, FAILURE),
    }.items()
}


def scenario(name: str, version: int) -> Scenario | None:
    return SCENARIOS.get((name, version))
