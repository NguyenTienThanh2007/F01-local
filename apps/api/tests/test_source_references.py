import json

from f01.application.source_artifacts import apply_proposal
from f01.domain.source import PutFile, SourceArtifact, SourceProposal
from f01.execution.source_references import build_source_hints, missing_stylesheet_hints, typecheck_source_hints
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


def test_global_css_module_hints_reproduce_real_storefront_build_failure() -> None:
    source = artifact("export default function Layout(){return null}",
        (PutFile(operation="put", path="app/page.module.css", prior_sha256=None,
            content="/* Design tokens */\n:root {--accent:red}\nbody {margin:0}\n.card h1 {color:red}"),))
    hints = tuple(map(json.loads, build_source_hints(source)))
    assert hints == ({"kind":"static_source_hint","code":"SOURCE_CSS_MODULE_GLOBAL_RULE",
        "path":"app/page.module.css","line":2,"selector":":root"},
        {"kind":"static_source_hint","code":"SOURCE_CSS_MODULE_GLOBAL_RULE",
        "path":"app/page.module.css","line":3,"selector":"body"})


def test_plain_global_stylesheets_and_scoped_module_rules_are_not_flagged() -> None:
    source = artifact("import './globals.css';",(
        PutFile(operation="put", path="app/globals.css", prior_sha256=None, content=":root{--accent:red}body{margin:0}"),
        PutFile(operation="put", path="app/page.module.css", prior_sha256=None, content=".page{--accent:red}\n.page h1{color:red}")))
    assert build_source_hints(source) == ()


def test_nullable_ref_and_native_event_hints_reproduce_social_compiler_failures() -> None:
    source = artifact("import React, { KeyboardEvent, useRef } from 'react';\n"
        "type Props = { ref?: React.RefObject<HTMLInputElement> | null };\n"
        "function trap(ref: React.RefObject<HTMLDivElement>){}\n"
        "document.addEventListener('keydown', (event: KeyboardEvent)=>{});")
    hints = tuple(map(json.loads, typecheck_source_hints(source, frozenset({"TS2345","TS2322","TS2769"}))))
    assert [(h['code'],h['line']) for h in hints] == [("SOURCE_NULLABLE_DOM_REF",2),
        ("SOURCE_NULLABLE_DOM_REF",3),("SOURCE_NATIVE_KEYBOARD_EVENT",1)]
    assert typecheck_source_hints(source, frozenset({"TS2588"})) == ()


def test_correct_nullable_refs_aliases_and_non_dom_types_are_not_flagged() -> None:
    source = artifact("import { KeyboardEvent as ReactKeyboardEvent } from 'react';\n"
        "type Props = { ref: React.RefObject<HTMLInputElement | null> };\n"
        "type Data = React.RefObject<string>;\n"
        "document.addEventListener('keydown', (event: globalThis.KeyboardEvent)=>{});")
    assert typecheck_source_hints(source,frozenset({"TS2322","TS2769"})) == ()


def test_typecheck_hints_stay_within_remaining_repair_slots() -> None:
    source = artifact("\n".join(f'type Ref{i} = React.RefObject<HTMLDivElement>;' for i in range(30)))
    hints = typecheck_source_hints(source,frozenset({"TS2345"}))
    assert len(hints) == 7 and all(len(h.encode()) < 2000 for h in hints)
