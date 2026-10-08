import asyncio
from uuid import UUID
import httpx
import pytest
from f01.execution.docker import DockerSandbox

from scripts.disposable_runtimes import RuntimeRecord, cleanup_disposable, remove_recorded

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


def test_repeated_interrupt_cannot_abandon_bounded_disposable_cleanup() -> None:
    import os
    import signal
    import subprocess
    import sys
    from pathlib import Path
    script = "from scripts.disposable_runtimes import protect_disposable_cleanup; import time; protect_disposable_cleanup(); print('cleanup-started',flush=True); time.sleep(.4); print('cleanup-confirmed',flush=True)"
    process = subprocess.Popen([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == 'cleanup-started'
        os.kill(process.pid, signal.SIGINT)
        os.kill(process.pid, signal.SIGINT)
        output, _ = process.communicate(timeout=5)
        assert process.returncode == 0 and 'cleanup-confirmed' in output
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_terminal_interrupt_keeps_disposable_database_available_for_cleanup() -> None:
    import os
    import signal
    import subprocess
    import sys
    from pathlib import Path
    script = """from pathlib import Path
import signal,time,psycopg
from scripts.test_database import test_database
with test_database(Path.cwd()) as url:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    print('database-ready',flush=True)
    time.sleep(.5)
    with psycopg.connect(url.replace('postgresql+psycopg://','postgresql://')) as connection:
        assert connection.execute('SELECT 1').fetchone() == (1,)
    print('database-available-for-cleanup',flush=True)
"""
    process = subprocess.Popen([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[3], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == 'database-ready'
        os.killpg(process.pid, signal.SIGINT)
        output, error = process.communicate(timeout=20)
        assert process.returncode == 0 and 'database-available-for-cleanup' in output, error
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_package_manager_terminate_cannot_abandon_started_cleanup() -> None:
    import os
    import signal
    import subprocess
    import sys
    from pathlib import Path
    script = "from scripts.disposable_runtimes import protect_disposable_cleanup; import time; protect_disposable_cleanup(); print('cleanup-started',flush=True); time.sleep(.4); print('cleanup-confirmed',flush=True)"
    process = subprocess.Popen([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == 'cleanup-started'
        os.kill(process.pid, signal.SIGTERM)
        output, _ = process.communicate(timeout=5)
        assert process.returncode == 0 and 'cleanup-confirmed' in output
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
