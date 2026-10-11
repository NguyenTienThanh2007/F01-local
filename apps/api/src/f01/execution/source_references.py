"""Bounded source-only repair hints. Never evaluate source or read host files.

These hints supplement a real failed build, not a complete JavaScript resolver or
compiler diagnostic. Docker evidence remains immutable and authoritative.
"""
import json
import posixpath
import re

from f01.domain.source import SourceArtifact, validate_source_path

_CSS_IMPORT = re.compile(
    r"(?m)^[ \t]*import[ \t]+(?:[A-Za-z_$][\w$]*[ \t]+from[ \t]+)?"
    r"(?P<quote>['\"])(?P<reference>\.{1,2}/[A-Za-z0-9_./\[\]()-]+\.css)(?P=quote)[ \t]*;?"
)


def missing_stylesheet_hints(source: SourceArtifact) -> tuple[str, ...]:
    files = {file.path for file in source.files}
    hints: list[str] = []
    seen: set[tuple[str, str]] = set()
    for file in source.files:
        if not file.path.endswith((".ts", ".tsx")):
            continue
        for match in _CSS_IMPORT.finditer(file.content):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(file.path), match["reference"]))
            try:
                validate_source_path(target)
            except ValueError:
                continue
            if target in files or (file.path, target) in seen:
                continue
            seen.add((file.path, target))
            hints.append(json.dumps({"kind": "static_source_hint", "code": "SOURCE_STYLESHEET_MISSING",
                "importer": file.path, "line": file.content.count("\n", 0, match.start()) + 1,
                "missing_path": target}, separators=(",", ":")))
            # Original command evidence occupies one of the eight context slots.
            if len(hints) == 7:
                return tuple(hints)
    return tuple(hints)
