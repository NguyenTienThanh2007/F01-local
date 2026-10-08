"""Portable host-tool discovery: Actions has pg_config but not initdb in PATH."""
import importlib.util
import shutil
import subprocess
from pathlib import Path
from types import ModuleType
import pytest


@pytest.fixture
def database_tools() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / 'scripts/test_database.py'
    spec = importlib.util.spec_from_file_location('disposable_database_tools', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pg_config_discovers_server_binaries_without_initdb_in_path(database_tools: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pg_config = shutil.which('pg_config')
    assert pg_config is not None, 'Local PostgreSQL tooling is required for the signal regression.'
    expected = Path(subprocess.run([pg_config, '--bindir'], check=True, capture_output=True, text=True, timeout=5).stdout.strip())
    monkeypatch.delenv('F01_TEST_PG_BIN', raising=False)
    monkeypatch.setattr(database_tools.shutil, 'which', lambda tool: pg_config if tool == 'pg_config' else None)
    assert database_tools.postgres_bin(tmp_path) == expected


def test_invalid_explicit_binary_override_fails_without_silent_fallback(database_tools: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('F01_TEST_PG_BIN', str(tmp_path / 'missing'))
    with pytest.raises(RuntimeError, match='initdb and postgres'):
        database_tools.postgres_bin(tmp_path)


def test_nested_disposable_databases_have_independent_server_logs(database_tools: ModuleType, tmp_path: Path) -> None:
    with database_tools.test_database(tmp_path) as first:
        with database_tools.test_database(tmp_path) as second:
            assert first != second
            logs = list((tmp_path / '.runtime').glob('test-postgres-*.log'))
            assert len(logs) == 2
    assert all(b'\x00' not in log.read_bytes() for log in logs)
