import io
import json
import tarfile
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from f01.application.source_artifacts import SourceRejected, apply_proposal, inspect_source_archive, package_source, sha256, validate_artifact
from f01.domain.source import DeleteFile, GenerationContext, PutFile, SourceProposal, validate_source_path
from f01.domain.planning import ProjectPlan
from tests.source_fixture import generation_context, initial_proposal, lineage


@pytest.mark.parametrize("path", [
    "../../private.ts", "/app/page.tsx", "app/../page.tsx", "app/./page.tsx", "app//page.tsx",
    "app\\page.tsx", "C:/app/page.tsx", "//host/app/page.tsx", "app/\x00page.tsx", "app/.env",
    "package.json", "app/package.json", "lib/pnpm-lock.yaml", "app/-inject.ts", "lib/CON.ts", "lib/lpt9.ts",
    "app/file.ts.", "app/é.tsx", "tests/anything.mjs", "app/tool.sh", "lib/node_modules/.bin/node", "app/" + "a" * 81 + ".tsx",
])
def test_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError):
        validate_source_path(path)


def test_content_is_exact_and_packaging_is_deterministic() -> None:
    proposal = initial_proposal()
    exact = "\n  export default function Page() { return <main>こんにちは</main>; }\n\n"
    proposal = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=None, edits=(
        proposal.edits[0], PutFile(operation="put", path="app/page.tsx", prior_sha256=None, content=exact)))
    first = apply_proposal(proposal, lineage())
    reversed_edits = proposal.model_copy(update={"edits": tuple(reversed(proposal.edits))})
    second = apply_proposal(reversed_edits, lineage())
    assert first == second
    assert next(f.content for f in first.files if f.path == "app/page.tsx") == exact
    raw = package_source(first)
    assert raw == package_source(second)
    assert inspect_source_archive(raw) == first.files
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        assert all(entry.mode == 0o644 and entry.uid == 10000 and entry.mtime == 0 for entry in archive)


def test_patch_preserves_unedited_content_and_pins_lineage() -> None:
    base = apply_proposal(initial_proposal(), lineage())
    original = {f.path: f for f in base.files}
    proposal = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=base.digest, edits=(
        PutFile(operation="put", path="app/page.tsx", prior_sha256=original["app/page.tsx"].sha256, content="New content\n"),))
    updated = apply_proposal(proposal, lineage(True), base=base)
    assert updated.parent_digest == base.digest and updated.lineage.version_id == UUID(int=5)
    assert updated.digest != base.digest
    assert next(f for f in updated.files if f.path == "app/layout.tsx") == original["app/layout.tsx"]
    assert next(f for f in base.files if f.path == "app/page.tsx").content != "New content\n"
    with pytest.raises(ValidationError):
        updated.digest = base.digest  # type: ignore[misc]


@pytest.mark.parametrize("conflict", ["digest", "file", "project", "version"])
def test_stale_and_foreign_source_inputs_rejected(conflict: str) -> None:
    base = apply_proposal(initial_proposal(), lineage())
    input_lineage = lineage(True)
    edit = PutFile(operation="put", path="app/page.tsx", prior_sha256=base.files[1].sha256, content="Update")
    proposal = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=base.digest, edits=(edit,))
    if conflict == "digest":
        proposal = proposal.model_copy(update={"base_digest": "0" * 64})
    if conflict == "file":
        proposal = proposal.model_copy(update={"edits": (edit.model_copy(update={"prior_sha256": "0" * 64}),)})
    if conflict == "project":
        input_lineage = input_lineage.model_copy(update={"project_id": UUID(int=99)})
    if conflict == "version":
        input_lineage = lineage()
    with pytest.raises(SourceRejected):
        apply_proposal(proposal, input_lineage, base=base)


def test_hash_tampering_is_not_accepted_as_source_evidence() -> None:
    base = apply_proposal(initial_proposal(), lineage())
    bad = base.model_copy(update={"files": (base.files[0].model_copy(update={"content": "tampered"}), base.files[1])})
    with pytest.raises(SourceRejected):
        validate_artifact(bad)
    bad_path = base.model_copy(update={"files": (base.files[0].model_copy(update={"path": "../../escape.ts"}), base.files[1])})
    with pytest.raises(SourceRejected):
        package_source(bad_path)


def test_delete_missing_entrypoint_and_noop_rejected() -> None:
    base = apply_proposal(initial_proposal(), lineage())
    for edit in (
        DeleteFile(operation="delete", path="app/page.tsx", prior_sha256=base.files[1].sha256),
        DeleteFile(operation="delete", path="components/missing.tsx", prior_sha256="0" * 64),
        PutFile(operation="put", path="app/page.tsx", prior_sha256=base.files[1].sha256, content=base.files[1].content),
    ):
        proposal = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=base.digest, edits=(edit,))
        with pytest.raises(SourceRejected):
            apply_proposal(proposal, lineage(True), base=base)


def test_optional_file_can_be_deleted_without_rewriting_other_files() -> None:
    initial = initial_proposal()
    initial = initial.model_copy(update={"edits": (*initial.edits, PutFile(operation="put", path="components/old.tsx", prior_sha256=None, content="old"))})
    base = apply_proposal(initial, lineage())
    proposal = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=base.digest, edits=(
        DeleteFile(operation="delete", path="components/old.tsx", prior_sha256=sha256("old")),))
    result = apply_proposal(proposal, lineage(True), base=base)
    assert {f.path for f in result.files} == {"app/layout.tsx", "app/page.tsx"}


def test_utf8_byte_limits_aggregate_limits_and_duplicate_edits() -> None:
    with pytest.raises(ValidationError):
        PutFile(operation="put", path="app/page.tsx", prior_sha256=None, content="界" * 22000)
    with pytest.raises(ValidationError):
        PutFile(operation="put", path="app/page.tsx", prior_sha256=None, content="bad\x00text")
    initial = initial_proposal()
    with pytest.raises(SourceRejected):
        apply_proposal(initial.model_copy(update={"edits": (initial.edits[0], initial.edits[0])}), lineage())
    edits = tuple(PutFile(operation="put", path=f"lib/file{i}.ts", prior_sha256=None, content="x" * 65536) for i in range(9))
    with pytest.raises(ValidationError):
        SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=None, edits=edits)


def test_snapshot_total_limit_cannot_be_bypassed_with_small_patches() -> None:
    initial = initial_proposal()
    base = apply_proposal(initial, lineage())
    for index in range(7):
        patch = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=base.digest, edits=(
            PutFile(operation="put", path=f"lib/file{index}.ts", prior_sha256=None, content="x" * 65536),))
        base = apply_proposal(patch, lineage(True), base=base)
    patch = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=base.digest, edits=(
        PutFile(operation="put", path="lib/overflow.ts", prior_sha256=None, content="x" * 65536),))
    with pytest.raises(SourceRejected):
        apply_proposal(patch, lineage(True), base=base)


def test_case_collisions_commands_and_credentials_rejected() -> None:
    initial = initial_proposal()
    raw = json.loads(initial.model_dump_json())
    raw["commands"] = ["echo injected"]
    with pytest.raises(ValidationError):
        SourceProposal.model_validate_json(json.dumps(raw))
    edits = (*initial.edits, PutFile(operation="put", path="components/Card.tsx", prior_sha256=None, content="a"),
             PutFile(operation="put", path="components/card.tsx", prior_sha256=None, content="b"))
    with pytest.raises(SourceRejected):
        apply_proposal(initial.model_copy(update={"edits": edits}), lineage())
    with pytest.raises(SourceRejected) as error:
        apply_proposal(initial, lineage(), forbidden_secrets=("Hello",))
    assert "Hello" not in str(error.value)


@pytest.mark.parametrize("kind", ["traversal", "symlink", "hardlink", "device", "duplicate", "oversize", "pax"])
def test_archive_cannot_escape_filesystem(tmp_path: Path, kind: str) -> None:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as archive:
        entry = tarfile.TarInfo("../../escape.ts" if kind == "traversal" else "app/page.tsx")
        if kind in {"symlink", "hardlink"}:
            entry.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
            entry.linkname = "/host/private"
        if kind == "device":
            entry.type = tarfile.CHRTYPE
        if kind == "pax":
            entry.pax_headers = {"path": "../../escape.ts"}
        content = b"x" * (65537 if kind == "oversize" else 1)
        if entry.isreg():
            entry.size = len(content)
        archive.addfile(entry, io.BytesIO(content) if entry.isreg() else None)
        if kind == "duplicate":
            archive.addfile(entry, io.BytesIO(content))
    with pytest.raises(SourceRejected):
        inspect_source_archive(out.getvalue())
    assert list(tmp_path.iterdir()) == []


def test_accumulated_file_count_limit_and_inherited_secret_rejection() -> None:
    base = apply_proposal(initial_proposal(), lineage())
    for start, count in ((0, 32), (32, 32), (64, 32), (96, 30)):
        edits = tuple(PutFile(operation="put", path=f"lib/file{i}.ts", prior_sha256=None, content="small") for i in range(start, start + count))
        patch = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=base.digest, edits=edits)
        base = apply_proposal(patch, lineage(True), base=base)
    patch = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=base.digest, edits=(
        PutFile(operation="put", path="lib/extra.ts", prior_sha256=None, content="small"),))
    with pytest.raises(SourceRejected):
        apply_proposal(patch, lineage(True), base=base)
    patch = SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=base.digest, edits=(
        PutFile(operation="put", path="lib/file0.ts", prior_sha256=sha256("small"), content="changed"),))
    with pytest.raises(SourceRejected):
        apply_proposal(patch, lineage(True), base=base, forbidden_secrets=("Hello",))


def test_context_requires_valid_brain_plan_bounded_history_and_same_project(project_plan: ProjectPlan) -> None:
    context = generation_context(project_plan)
    for changes in ({"brain_json": "{}"}, {"approved_plan_json": "{}"}, {"relevant_history": ("x" * 2001,)}, {"lineage": lineage(True)}):
        with pytest.raises(ValidationError):
            GenerationContext.model_validate_json(context.model_copy(update=changes).model_dump_json())
    base = apply_proposal(initial_proposal(), lineage())
    foreign = context.model_copy(update={"lineage": lineage(True).model_copy(update={"project_id": UUID(int=99)}), "base_source": base})
    with pytest.raises(ValidationError):
        GenerationContext.model_validate_json(foreign.model_dump_json())
