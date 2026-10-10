from contextlib import contextmanager
from collections.abc import Iterator
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import asyncio
from uuid import UUID
import httpx
import pytest
from f01.execution.docker import DockerSandbox

from scripts.disposable_runtimes import RuntimeRecord, cleanup_disposable, remove_recorded

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]

IMAGE='sha256:'+'a'*64
NAME='f01-'+'b'*32+'-1-1'
PROJECT,RUN=UUID(int=1),UUID(int=2)

@pytest.mark.parametrize('foreign',[None,'project','run','image'])
def test_cleanup_only_removes_matching_recorded_runtime(foreign:str|None)->None:
    calls:list[str]=[]
    def response(request:httpx.Request)->httpx.Response:
        calls.append(request.method)
        if request.method=='GET':return httpx.Response(200,json={'Image':IMAGE if foreign!='image' else 'other','Config':{'Labels':{'f01.role':'candidate','f01.project_id':str(PROJECT if foreign!='project' else UUID(int=3)),'f01.run_id':str(RUN if foreign!='run' else UUID(int=4))}}})
        return httpx.Response(204)
    async def check()->None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(response),base_url='http://docker') as client:
            sandbox=DockerSandbox(client,IMAGE)
            records=[RuntimeRecord(NAME,PROJECT,RUN)]*2
            if foreign:
                with pytest.raises(RuntimeError,match='SCOPE_MISMATCH'):await remove_recorded(sandbox,records)
                assert calls==['GET']
            else:
                assert await remove_recorded(sandbox,records)==1 and calls==['GET','DELETE']
    asyncio.run(check())

def test_cleanup_rejects_non_disposable_database_before_docker_access()->None:
    with pytest.raises(RuntimeError,match='DISPOSABLE_DATABASE_REQUIRED'):
        asyncio.run(cleanup_disposable('postgresql+psycopg://owner@127.0.0.1/production','/unavailable','unused'))


# A byte-level pipe protocol avoids TextIO prefetch, hidden stderr and unbounded
# readline waits. Markers, rather than sleeps, order readiness/signal/checks.


class ChildProtocol:
    def __init__(self, script: str, cwd: Path) -> None:
        self.process = subprocess.Popen([sys.executable, '-u', '-c', script], cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        self.output = b''
        self.pending = b''
        self.finished = False

    def wait_for(self, expected: str, timeout: float = 20) -> None:
        assert self.process.stdout is not None
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while True:
                while b'\n' in self.pending:
                    line, self.pending = self.pending.split(b'\n', 1)
                    if line.decode().strip() == expected:
                        return
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise AssertionError(f'Timed out waiting for {expected}:\n{self.output.decode()}')
                chunk = os.read(self.process.stdout.fileno(), 4096)
                if not chunk:
                    code = self.process.wait(timeout=5)
                    raise AssertionError(f'Child exited before {expected} (exit {code}):\n{self.output.decode()}')
                self.output += chunk
                self.pending += chunk

    def finish(self, command: bytes = b'finish\n') -> None:
        output, _ = self.process.communicate(input=command, timeout=20)
        self.output += output
        self.finished = True
        assert self.process.returncode == 0, self.output.decode()

    def close(self) -> None:
        try:
            if not self.finished:
                # EOF first lets a child unwind its DB context even if the test
                # assertion failed. TERM then KILL apply only to this owned child.
                if self.process.stdin is not None:
                    self.process.stdin.close()
                    self.process.stdin = None
                try:
                    output, _ = self.process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.terminate()
                    try:
                        output, _ = self.process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        output, _ = self.process.communicate(timeout=5)
                self.output += output
        finally:
            if self.process.stdout is not None:
                self.process.stdout.close()


@contextmanager
def child_protocol(script: str, cwd: Path = API_ROOT) -> Iterator[ChildProtocol]:
    child = ChildProtocol(script, cwd)
    try:
        yield child
    finally:
        child.close()


def check_cleanup_signals(signals: tuple[int, ...]) -> None:
    script = "from scripts.disposable_runtimes import protect_disposable_cleanup; import sys; protect_disposable_cleanup(); print('cleanup-started',flush=True); sys.stdin.readline(); print('cleanup-confirmed',flush=True)"
    with child_protocol(script) as child:
        child.wait_for('cleanup-started')
        for signum in signals:
            os.kill(child.process.pid, signum)
        child.finish()
        assert b'cleanup-confirmed' in child.output


def test_repeated_interrupt_cannot_abandon_bounded_disposable_cleanup() -> None:
    check_cleanup_signals((signal.SIGINT, signal.SIGINT))


def test_package_manager_terminate_cannot_abandon_started_cleanup() -> None:
    check_cleanup_signals((signal.SIGTERM,))


DATABASE_SCRIPT = r"""from pathlib import Path
import os,signal,sys,psycopg
sys.path.insert(0,str(Path.cwd()/'scripts'))
from test_database import test_database
# TERM during failed startup/readiness must also unwind an acquired DB context.
def shutdown(signum,frame):
    raise SystemExit(1)
signal.signal(signal.SIGTERM,shutdown)
with test_database(Path.cwd()) as url:
    with psycopg.connect(url.replace('postgresql+psycopg://','postgresql://'),connect_timeout=3) as connection:
        backend_pid = connection.execute('SELECT pg_backend_pid()').fetchone()[0]
        assert os.getpgid(backend_pid) != os.getpgrp(), 'PostgreSQL shares terminal process group'
    # os.write avoids reentrant buffered stdio inside the signal handler.
    signal.signal(signal.SIGINT,lambda signum,frame:os.write(1,b'interrupt-observed\n'))
    print('database-ready',flush=True)
    if sys.stdin.readline() == 'check\n':
        with psycopg.connect(url.replace('postgresql+psycopg://','postgresql://'),connect_timeout=3) as connection:
            assert connection.execute('SELECT 1').fetchone() == (1,)
        print('database-available-for-cleanup',flush=True)
print('database-cleanup-complete',flush=True)
"""


def test_terminal_interrupt_keeps_disposable_database_available_for_cleanup() -> None:
    with child_protocol(DATABASE_SCRIPT, REPO_ROOT) as child:
        child.wait_for('database-ready')
        os.killpg(child.process.pid, signal.SIGINT)
        child.wait_for('interrupt-observed')
        child.finish(b'check\n')
        assert b'database-available-for-cleanup' in child.output
        assert b'database-cleanup-complete' in child.output


def test_failed_parent_assertion_still_closes_disposable_database() -> None:
    with pytest.raises(ValueError, match='interrupted review'):
        with child_protocol(DATABASE_SCRIPT, REPO_ROOT) as child:
            child.wait_for('database-ready')
            raise ValueError('interrupted review')
    assert child.process.returncode == 0
    assert b'database-cleanup-complete' in child.output


def test_startup_exit_reports_stderr_and_return_code() -> None:
    with child_protocol("import sys; print('initdb-unavailable',file=sys.stderr,flush=True); sys.exit(17)") as child:
        with pytest.raises(AssertionError, match=r'Child exited before database-ready \(exit 17\):\ninitdb-unavailable'):
            child.wait_for('database-ready')
    assert child.process.returncode == 17


def test_partial_readiness_output_is_bounded_and_child_is_reaped() -> None:
    with child_protocol("import sys; sys.stdout.write('partial marker'); sys.stdout.flush(); sys.stdin.read()") as child:
        with pytest.raises(AssertionError, match='Timed out waiting for database-ready:'):
            child.wait_for('database-ready', timeout=.1)
    assert child.process.returncode == 0
    assert b'partial marker' in child.output


def test_buffered_readiness_markers_are_not_lost() -> None:
    with child_protocol("import sys; sys.stdout.write('starting\\nready\\n'); sys.stdout.flush(); sys.stdin.readline()") as child:
        child.wait_for('starting')
        child.wait_for('ready')
        child.finish()


def test_database_startup_failure_exposes_missing_tool_diagnostic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('F01_TEST_PG_BIN', str(tmp_path / 'unavailable'))
    with child_protocol(DATABASE_SCRIPT, REPO_ROOT) as child:
        with pytest.raises(AssertionError, match='Set F01_TEST_PG_BIN to the directory containing initdb and postgres'):
            child.wait_for('database-ready')
    assert child.process.returncode == 1
