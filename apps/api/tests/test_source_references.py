import json

from f01.application.source_artifacts import apply_proposal
from f01.domain.source import PutFile, SourceArtifact, SourceProposal
from f01.execution.source_references import missing_stylesheet_hints
from tests.source_fixture import lineage


def artifact(layout: str, extras: tuple[PutFile, ...] = ()) -> SourceArtifact:
    return apply_proposal(SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=None,
        edits=(PutFile(operation="put", path="app/layout.tsx", prior_sha256=None, content=layout),
            PutFile(operation="put", path="app/page.tsx", prior_sha256=None, content="export default function Page(){return null}"), *extras)), lineage())


def test_missing_stylesheet_repair_hint_reproduces_real_analytics_failure() -> None:
    source = artifact("import React from 'react';\nimport './globals.css';\nexport default function Layout(){return null}")
    assert tuple(map(json.loads, missing_stylesheet_hints(source))) == ({"kind": "static_source_hint",
        "code": "SOURCE_STYLESHEET_MISSING", "importer": "app/layout.tsx", "line": 2, "missing_path": "app/globals.css"},)
    assert source.files[0].content.startswith("import React")  # Observational; never rewrites source.


def test_present_stylesheets_and_nonlocal_dependencies_do_not_produce_hints() -> None:
    source = artifact("import './globals.css';\nimport 'package/styles.css';\nimport 'https://example.test/private.css';",
        (PutFile(operation="put", path="app/globals.css", prior_sha256=None, content="body{margin:0}"),))
    assert missing_stylesheet_hints(source) == ()


def test_css_module_paths_are_normalized_only_inside_validated_editable_roots() -> None:
    source = artifact("import styles from '../styles/card.module.css';\nimport '../../private/password.css';\nimport '/etc/secret.css';\nimport './.env';")
    hints = tuple(map(json.loads, missing_stylesheet_hints(source)))
    assert len(hints) == 1 and hints[0]["missing_path"] == "styles/card.module.css"
    assert "password" not in "".join(missing_stylesheet_hints(source))


def test_hints_are_deduplicated_and_bounded_to_remaining_repair_context_slots() -> None:
    source = artifact("import './file0.css';\n" + "\n".join(f"import './file{i}.css';" for i in range(20)))
    hints = missing_stylesheet_hints(source)
    assert len(hints) == 7 and all(len(hint.encode()) < 2000 for hint in hints)
    assert len({json.loads(hint)["missing_path"] for hint in hints}) == 7
