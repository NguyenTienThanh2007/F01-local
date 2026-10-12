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
_GLOBAL_SELECTOR = re.compile(r"(?m)^[ \t]*(?P<selector>:root|html|body)[ \t]*(?:\{|,)")
_NONNULL_DOM_REF = re.compile(r"\b(?:React\.)?RefObject\s*<\s*(?P<element>HTML[A-Za-z]*Element)\s*>")
_REACT_KEYBOARD_IMPORT = re.compile(r"import\s+(?:[^;]*?\{)[^}]*\bKeyboardEvent\s*(?:,|\})[^;]*?from\s*['\"]react['\"]")


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


def build_source_hints(source: SourceArtifact) -> tuple[str, ...]:
    """Nonblocking literal-source hints for an observed failed production build."""
    hints = list(missing_stylesheet_hints(source))
    for file in source.files:
        if len(hints) == 7:
            break
        if not file.path.endswith(".module.css"):
            continue
        for match in _GLOBAL_SELECTOR.finditer(file.content):
            if len(hints) == 7:
                break
            hints.append(json.dumps({"kind": "static_source_hint", "code": "SOURCE_CSS_MODULE_GLOBAL_RULE",
                "path": file.path, "line": file.content.count("\n", 0, match.start()) + 1,
                "selector": match["selector"]}, separators=(",", ":")))
    return tuple(hints)


def typecheck_source_hints(source: SourceArtifact, codes: frozenset[str]) -> tuple[str, ...]:
    """Literal clues for observed assignability errors; never compiler-log contents."""
    hints: list[str] = []
    for file in source.files:
        if not file.path.endswith((".ts", ".tsx")):
            continue
        if codes & {"TS2322", "TS2345"}:
            for match in _NONNULL_DOM_REF.finditer(file.content):
                hints.append(json.dumps({"kind":"static_source_hint", "code":"SOURCE_NULLABLE_DOM_REF",
                    "path":file.path, "line":file.content.count("\n",0,match.start())+1,
                    "element":match["element"]}, separators=(",", ":")))
                if len(hints) == 7:
                    return tuple(hints)
        if "TS2769" in codes and "addEventListener" in file.content:
            keyboard_match = _REACT_KEYBOARD_IMPORT.search(file.content)
            if keyboard_match:
                hints.append(json.dumps({"kind":"static_source_hint", "code":"SOURCE_NATIVE_KEYBOARD_EVENT",
                    "path":file.path, "line":file.content.count("\n",0,keyboard_match.start())+1}, separators=(",", ":")))
                if len(hints) == 7:
                    return tuple(hints)
    return tuple(hints)
