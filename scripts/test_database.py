"""Disposable local PostgreSQL for factory tests; never reads DATABASE_URL."""
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
import os
import shutil
import socket
import subprocess
import tempfile
import time

import psycopg


def postgres_bin(root: Path) -> Path:
    """Resolve host server tools, including Debian's non-PATH PostgreSQL bindir."""
    configured = os.environ.get('F01_TEST_PG_BIN')
    if configured:
        directory = Path(configured)
    else:
        bundled = root / '.runtime/postgres/usr/lib/postgresql/16/bin'
        found = shutil.which('initdb')
        pg_config = shutil.which('pg_config')
        if bundled.exists():
            directory = bundled
        elif found:
            directory = Path(found).parent
        elif pg_config:
            result = subprocess.run([pg_config, '--bindir'], check=True, capture_output=True, text=True, timeout=5)
            directory = Path(result.stdout.strip())
        else:
            directory = Path('/Library/PostgreSQL/18/bin')
    if not all((directory / tool).is_file() for tool in ('initdb', 'postgres')):
        raise RuntimeError('Set F01_TEST_PG_BIN to the directory containing initdb and postgres.')
    return directory


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


@contextmanager
def test_database(root: Path) -> Iterator[str]:
    bundled = root / '.runtime/postgres/usr/lib/postgresql/16/bin'
    pg_bin = postgres_bin(root)
    env = dict(os.environ)
    if pg_bin == bundled:
        env.update(LD_LIBRARY_PATH=str(root / '.runtime/postgres/usr/lib/x86_64-linux-gnu'), LD_PRELOAD=str(root / '.runtime/postgres-identity.so'))
    runtime = root / '.runtime'
    runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='f01-test-') as temporary:
        data = Path(temporary) / 'data'
        subprocess.run([str(pg_bin / 'initdb'), '-D', str(data), '-U', 'f01_test', '--auth=trust', '--no-locale', '--encoding=UTF8'], env=env, check=True, stdout=subprocess.DEVNULL)
        port = free_port()
        # Nested signal tests must not truncate the outer regression DB's log.
        log_path = runtime / f'test-postgres-{Path(temporary).name}.log'
        with log_path.open('w') as log:
            pg = subprocess.Popen([str(pg_bin / 'postgres'), '-D', str(data), '-h', '127.0.0.1', '-p', str(port), '-c', 'unix_socket_directories=', '-c', 'jit=off', '-c', 'timezone=UTC'], env=env, stdout=log, stderr=log, start_new_session=True)  # Keep terminal Ctrl+C from stopping the DB before recorded-runtime cleanup.
            try:
                for _ in range(100):
                    try:
                        with psycopg.connect(host='127.0.0.1', port=port, user='f01_test', dbname='postgres', autocommit=True) as connection:
                            connection.execute('CREATE DATABASE f01_test_acceptance')
                        break
                    except psycopg.OperationalError:
                        if pg.poll() is not None:
                            raise RuntimeError(f'Test PostgreSQL exited; inspect {log_path}.') from None
                        time.sleep(.1)
                else:
                    raise RuntimeError('Test PostgreSQL did not start.')
                yield f'postgresql+psycopg://f01_test@127.0.0.1:{port}/f01_test_acceptance'
            finally:
                pg.terminate()
                pg.wait(timeout=15)
