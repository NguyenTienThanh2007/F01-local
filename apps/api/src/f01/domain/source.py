"""Untrusted source proposals. These values grant no filesystem or execution rights."""
import re
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator

from f01.domain.brain import BrainContent
from f01.domain.context_planning import ContextPlan

MAX_FILE_BYTES = 65536
MAX_SOURCE_BYTES = 524288
MAX_SOURCE_FILES = 128
MAX_EDITS = 32
_ROOTS = {"app", "components", "lib", "styles", "public", "tests"}
_PROTECTED = {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def validate_source_path(value: str) -> str:
    """Portable, relative, explicitly editable paths; no normalization of bad input."""
    parts = value.split("/")
    if (
        len(value) > 240
        or len("/".join(parts[:-1])) > 155
        or len(parts) < 2
        or len(parts) > 12
        or parts[0] not in _ROOTS
        or any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.\[\]()-]*", p) for p in parts)
        or any(len(p) > 80 for p in parts)
        or any(p.endswith(".") or p.split(".")[0].lower() in _RESERVED for p in parts)
        or any(p.lower() in _PROTECTED for p in parts)
    ):
        raise ValueError("Source path is outside the editable policy.")
    suffix = parts[-1].rsplit(".", 1)[-1]
    if parts[0] == "tests":
        if not parts[-1].endswith(".test.mjs"):
            raise ValueError("Only explicit Node test files are editable under tests.")
    elif suffix not in {"ts", "tsx", "css", "json", "svg", "md"}:
        raise ValueError("Source file type is not supported.")
    return value


def validate_text(value: str) -> str:
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise ValueError("Source must be valid UTF-8 text.") from None
    if size > MAX_FILE_BYTES or "\x00" in value:
        raise ValueError("Source file exceeds the text policy.")
    return value


Path = Annotated[str, AfterValidator(validate_source_path)]
Content = Annotated[str, AfterValidator(validate_text)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class SourceModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, hide_input_in_errors=True)


class PutFile(SourceModel):
    operation: Literal["put"]
    path: Path
    prior_sha256: Digest | None
    content: Content


class DeleteFile(SourceModel):
    operation: Literal["delete"]
    path: Path
    prior_sha256: Digest


class SourceProposal(SourceModel):
    schema_version: Literal[1]
    recipe: Literal["next-web-v1"]
    base_digest: Digest | None
    edits: tuple[PutFile | DeleteFile, ...] = Field(min_length=1, max_length=MAX_EDITS)

    @model_validator(mode="after")
    def bounded_unique_edits(self) -> Self:
        paths = [edit.path.casefold() for edit in self.edits]
        if len(set(paths)) != len(paths):
            raise ValueError("Source edits must have unique portable paths.")
        if sum(len(edit.content.encode("utf-8")) for edit in self.edits if isinstance(edit, PutFile)) > MAX_SOURCE_BYTES:
            raise ValueError("Source proposal exceeds the aggregate limit.")
        return self


class SourceLineage(SourceModel):
    project_id: UUID
    request_id: UUID
    brain_revision_id: UUID
    plan_id: UUID
    version_id: UUID | None


class SourceFile(SourceModel):
    path: Path
    content: Content
    sha256: Digest


class SourceArtifact(SourceModel):
    """Immutable in-memory value, not a persisted or verified application version."""
    schema_version: Literal[1]
    recipe: Literal["next-web-v1"]
    lineage: SourceLineage
    parent_digest: Digest | None
    digest: Digest
    files: tuple[SourceFile, ...] = Field(min_length=1, max_length=MAX_SOURCE_FILES)


class GenerationContext(SourceModel):
    """Caller must authorize and check plan/context freshness before creating this value."""
    lineage: SourceLineage
    approved_brief: str = Field(min_length=1, max_length=10000)
    brain_json: str = Field(min_length=2, max_length=40000)
    approved_plan_json: str = Field(min_length=2, max_length=30000)
    requirements: tuple[str, ...] = Field(min_length=1, max_length=32)
    architecture: str = Field(min_length=1, max_length=8000)
    design_constraints: tuple[str, ...] = Field(max_length=16)
    relevant_history: tuple[str, ...] = Field(max_length=16)
    base_source: SourceArtifact | None
    repair_evidence: tuple[str, ...] = Field(max_length=8)

    @model_validator(mode="after")
    def bounded_context(self) -> Self:
        BrainContent.model_validate_json(self.brain_json)
        ContextPlan.model_validate_json(self.approved_plan_json)
        if any(len(item.encode("utf-8")) > 2000 for item in (*self.requirements, *self.design_constraints, *self.relevant_history, *self.repair_evidence)):
            raise ValueError("Context entry exceeds its limit.")
        if len(self.model_dump_json().encode("utf-8")) > 131072:
            raise ValueError("Generation context exceeds its limit.")
        if self.base_source is not None and self.base_source.lineage.project_id != self.lineage.project_id:
            raise ValueError("Source context belongs to another project.")
        if (self.lineage.version_id is None) != (self.base_source is None) and not (self.repair_evidence and self.base_source and self.base_source.lineage == self.lineage):
            raise ValueError("Existing-version context must pin a source artifact.")
        return self


class GenerationResult(SourceModel):
    proposal: SourceProposal
    input_tokens: int | None = Field(ge=0)
    output_tokens: int | None = Field(ge=0)
