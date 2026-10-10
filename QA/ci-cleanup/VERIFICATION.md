# CI disposable-cleanup regression fix

Continues remote commercial-v1 commit `e4960c023ad270668512d57b4307674397a38f4c`. Main and PR #1 remain unmerged.

The failed [Commercial regression run](https://github.com/NguyenTienThanh2007/F01-local/actions/runs/37802336014) reported 354 passing backend tests and one failure: `test_terminal_interrupt_keeps_disposable_database_available_for_cleanup` read EOF instead of `database-ready`. The previous assertion did not consume the child's separate stderr or report its exit status. EOF indicates the child exited; stdout buffering or slower startup would block that unbounded `readline`, not return an empty string.

The test creates its own **host** PostgreSQL instance, independently of the Actions service database. The backend workflow had not configured `F01_TEST_PG_BIN`; only its later browser command supplied `pg_config --bindir`. The helper searched PATH for `initdb`, then used a macOS fallback. Ubuntu's server binaries need their versioned bindir. The fix explicitly discovers and validates that directory in the backend job, and the helper supports `pg_config` when `initdb` is outside PATH. An invalid explicit override still fails; it never silently selects another database or skips the test.

Reproduction with an unavailable server-tool directory produced the identical empty readiness assertion. Direct child execution exposed the missing-`initdb`/`postgres` configuration exception. Regression now tests that failure path and includes its stderr and exit status. A separate regression resolves the actual installed `pg_config` while hiding `initdb` from PATH.

The old half-second delay was also an ordering race: a slow parent could send SIGINT after the child's check or exit. The replacement uses stdin/stdout handshakes: verify server readiness and independent process group → report ready → parent sends SIGINT to its owned child group → child acknowledges signal delivery → parent releases the real database query → confirm database availability → exit the database context → confirm cleanup. There are no guessed sleeps. The database's isolated session, real signal and real SQL query remain mandatory.

Readiness has a bounded deadline instead of an unbounded line read; existing completion deadlines were not enlarged. Byte-level pipe reads preserve prefetched markers and partial lines; stderr shares the diagnostic pipe. Failed parent assertions send EOF so the child unwinds its database context, with bounded owned-process TERM/KILL/reap fallback. The child handles TERM during startup to unwind any acquired database context. Cleanup continues to require exact recorded runtime/image/project/run labels and a disposable database; production execution behavior is unchanged.

Nested test databases previously truncated the same diagnostic file, producing sparse NUL-filled logs in the full run. Each disposable server now has an independent log and its startup exception points to that log. A real nested-database regression confirms independent logs and clean teardown.

Local acceptance:

- 16 affected subprocess/discovery tests, including real PostgreSQL/SIGINT, stderr/early exit, partial-output timeout, buffered markers, parent-failure cleanup, repeated INT/TERM, invalid override and independent logs.
- Full backend: **363 passed, 5 opt-in checks skipped**, one existing Starlette TestClient/httpx deprecation warning.
- Strict mypy: **108 source files**, passed using the same targets as Actions.

Logs are in this folder. Remote acceptance is the Commercial regression workflow on the pushed fix commit; its jobs cover backend/mypy, client drift, frontend tests, typecheck, production build and browser regression. Check the new commit's actual Actions conclusions before claiming green. The manually dispatched Docker workflow was not changed or dispatched by this CI fix.
