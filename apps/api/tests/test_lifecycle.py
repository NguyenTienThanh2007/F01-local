from uuid import uuid4

import pytest
from pydantic import ValidationError

from f01.domain.brain import BrainContent, Provenance, initial_brain
from f01.domain.lifecycle import (
    lifecycle_after_terminal,
    transition_phase,
    transition_status,
)


def test_lifecycle_transitions_require_ordered_phases_and_linked_repairs() -> None:
    assert transition_status("queued", "running") == "running"
    assert transition_phase(None, "understanding") == "understanding"
    assert (
        transition_phase("verifying", "building", repair_event_sequence=4) == "building"
    )
    for source, target in [
        ("succeeded", "running"),
        ("canceled", "succeeded"),
        ("queued", "succeeded"),
    ]:
        with pytest.raises(ValueError):
            transition_status(source, target)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        transition_phase("verifying", "building")
    with pytest.raises(ValueError):
        transition_phase("understanding", "deploying")
    assert lifecycle_after_terminal("canceled", has_version=False) == "idle"
    assert lifecycle_after_terminal("canceled", has_version=True) == "live"
    assert lifecycle_after_terminal("failed", has_version=True) == "error"


def test_brain_is_validated_proposed_context_with_stable_provenance() -> None:
    identifier = uuid4()
    brief = "Build a CRM for a small real estate agency."
    brain = initial_brain(identifier, brief)
    assert BrainContent.model_validate_json(brain.model_dump_json()) == brain
    assert brain.original_request_id == identifier
    assert brain.product.summary.text == brief
    assert brain.stack.frontend.provenance.source == "template"
    assert brain.product.requirements[0].assumption is True
    with pytest.raises(ValidationError):
        Provenance(source="simulation")
    invalid = brain.model_dump(mode="json")
    invalid["plan"][0]["dependencies"] = ["missing"]
    with pytest.raises(ValidationError):
        BrainContent.model_validate(invalid)
