"""Pure source validation and deterministic packaging; never writes model files to disk."""
import hashlib
import io
import json
import tarfile

from f01.domain.source import (
    DeleteFile, PutFile, SourceArtifact, SourceFile, SourceLineage, SourceProposal,
    MAX_SOURCE_BYTES, MAX_SOURCE_FILES, validate_source_path, validate_text,
)

REQUIRED_FILES = frozenset({"app/layout.tsx", "app/page.tsx"})
MAX_ARCHIVE_BYTES = 1048576


class SourceRejected(ValueError):
    """Owned diagnostic only; never includes source, paths or model errors."""


def sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _digest(lineage: SourceLineage, parent: str | None, files: tuple[SourceFile, ...]) -> str:
    manifest = {
        "schema_version": 1, "recipe": "next-web-v1", "lineage": lineage.model_dump(mode="json"),
        "parent_digest": parent,
        "files": [{"path": f.path, "sha256": f.sha256, "bytes": len(f.content.encode("utf-8"))} for f in files],
    }
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def validate_artifact(artifact: SourceArtifact) -> None:
    try:
        artifact = SourceArtifact.model_validate_json(artifact.model_dump_json())
    except ValueError:
        raise SourceRejected("Invalid source manifest.") from None
    paths = [f.path for f in artifact.files]
    if paths != sorted(paths) or len(set(p.casefold() for p in paths)) != len(paths):
        raise SourceRejected("Invalid source manifest.")
    if not REQUIRED_FILES <= set(paths) or sum(len(f.content.encode("utf-8")) for f in artifact.files) > MAX_SOURCE_BYTES:
        raise SourceRejected("Invalid source bounds or entrypoints.")
    if any(f.sha256 != sha256(f.content) for f in artifact.files) or artifact.digest != _digest(artifact.lineage, artifact.parent_digest, artifact.files):
        raise SourceRejected("Source digest does not match its contents.")


def apply_proposal(
    proposal: SourceProposal, lineage: SourceLineage, *,
    base: SourceArtifact | None = None, forbidden_secrets: tuple[str, ...] = (),
) -> SourceArtifact:
    """Compare-and-apply patch. Ownership/freshness must also be checked in the future transaction."""
    try:
        proposal = SourceProposal.model_validate_json(proposal.model_dump_json())
        lineage = SourceLineage.model_validate_json(lineage.model_dump_json())
    except ValueError:
        raise SourceRejected("Invalid source proposal.") from None
    if base is not None:
        validate_artifact(base)
    if proposal.base_digest != (base.digest if base else None):
        raise SourceRejected("Stale source base.")
    if base is not None and (base.lineage.project_id != lineage.project_id or lineage.version_id is None):
        raise SourceRejected("Source lineage conflict.")
    if base is None and lineage.version_id is not None:
        raise SourceRejected("Missing version source.")
    files = {f.path: f for f in base.files} if base else {}
    changed = False
    for edit in proposal.edits:
        prior = files.get(edit.path)
        if edit.prior_sha256 != (prior.sha256 if prior else None):
            raise SourceRejected("Stale file input.")
        if isinstance(edit, DeleteFile):
            if prior is None or edit.path in REQUIRED_FILES:
                raise SourceRejected("Invalid file deletion.")
            del files[edit.path]
            changed = True
        elif isinstance(edit, PutFile):
            if any(secret and secret in edit.content for secret in forbidden_secrets):
                raise SourceRejected("Forbidden secret in source.")
            changed = changed or prior is None or prior.content != edit.content
            files[edit.path] = SourceFile(path=edit.path, content=edit.content, sha256=sha256(edit.content))
    paths = list(files)
    if not changed or len(files) > MAX_SOURCE_FILES or not REQUIRED_FILES <= set(files):
        raise SourceRejected("Invalid source changes or entrypoints.")
    if len(set(p.casefold() for p in paths)) != len(paths):
        raise SourceRejected("Conflicting portable source paths.")
    if sum(len(f.content.encode("utf-8")) for f in files.values()) > MAX_SOURCE_BYTES:
        raise SourceRejected("Source exceeds aggregate size limit.")
    ordered = tuple(files[path] for path in sorted(files))
    if any(secret and secret in file.content for file in ordered for secret in forbidden_secrets):
        raise SourceRejected("Forbidden secret in source.")
    parent = base.digest if base else None
    artifact = SourceArtifact(schema_version=1, recipe="next-web-v1", lineage=lineage, parent_digest=parent,
                              digest=_digest(lineage, parent, ordered), files=ordered)
    validate_artifact(artifact)
    return artifact


def package_source(artifact: SourceArtifact) -> bytes:
    """Only generated text files. Trusted scaffold/dependencies must be provisioned separately."""
    validate_artifact(artifact)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for file in artifact.files:
            content = file.content.encode("utf-8")
            entry = tarfile.TarInfo(file.path)
            entry.size = len(content)
            entry.mode = 0o644
            entry.uid = entry.gid = 10000
            entry.mtime = 0
            archive.addfile(entry, io.BytesIO(content))
    raw = output.getvalue()
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise SourceRejected("Source archive exceeds limit.")
    return raw


def inspect_source_archive(raw: bytes) -> tuple[SourceFile, ...]:
    """Validate archive in memory. No extraction, links, devices or host filesystem access."""
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise SourceRejected("Source archive exceeds limit.")
    files: list[SourceFile] = []
    seen: set[str] = set()
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            for entry in archive:
                if not entry.isreg() or entry.pax_headers or not 0 <= entry.size <= 65536:
                    raise SourceRejected("Unsupported source archive entry.")
                path = validate_source_path(entry.name)
                if path.casefold() in seen or len(files) >= MAX_SOURCE_FILES:
                    raise SourceRejected("Duplicate or excessive source archive entries.")
                total += entry.size
                if total > MAX_SOURCE_BYTES:
                    raise SourceRejected("Source archive exceeds content limit.")
                stream = archive.extractfile(entry)
                if stream is None:
                    raise SourceRejected("Missing source archive entry.")
                with stream:
                    content = validate_text(stream.read(65537).decode("utf-8"))
                if len(content.encode("utf-8")) != entry.size:
                    raise SourceRejected("Truncated source archive entry.")
                files.append(SourceFile(path=path, content=content, sha256=sha256(content)))
                seen.add(path.casefold())
    except SourceRejected:
        raise
    except (tarfile.TarError, UnicodeError, ValueError, OSError):
        raise SourceRejected("Invalid source archive.") from None
    if not REQUIRED_FILES <= {f.path for f in files}:
        raise SourceRejected("Missing source entrypoints.")
    return tuple(sorted(files, key=lambda f: f.path))
