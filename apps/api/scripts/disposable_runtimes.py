"""Test tooling: cleanup only runtimes recorded in the launcher's disposable database."""
import json
import re
from dataclasses import dataclass
from uuid import UUID
import httpx
from sqlalchemy import select
from sqlalchemy.engine import make_url
from f01.db.models import ArtifactPreparation, ExecutionJob, IsolatedPreview, ProjectVersion
from f01.db.session import Database
from f01.execution.docker import DockerSandbox


@dataclass(frozen=True)
class RuntimeRecord:
    name: str
    project_id: UUID
    run_id: UUID


async def remove_recorded(sandbox: DockerSandbox, records: list[RuntimeRecord]) -> int:
    removed=0
    for record in {r.name:r for r in records}.values():
        if not re.fullmatch(r'f01-[a-f0-9]{32}-[0-9]+-[0-9]+',record.name):
            raise RuntimeError('DISPOSABLE_CLEANUP_ID_INVALID')
        raw=await sandbox.request('GET',f'/containers/{record.name}/json',missing_ok=True)
        if not raw:continue
        container=json.loads(raw);labels=container.get('Config',{}).get('Labels',{})
        if container.get('Image')!=sandbox.image or labels.get('f01.role')!='candidate' or labels.get('f01.project_id')!=str(record.project_id) or labels.get('f01.run_id')!=str(record.run_id):
            raise RuntimeError('DISPOSABLE_CLEANUP_SCOPE_MISMATCH')
        await sandbox.remove(record.name);removed+=1
    return removed


async def cleanup_disposable(database_url: str, socket: str, image: str) -> int:
    url=make_url(database_url)
    if url.host!='127.0.0.1' or url.username!='f01_test' or url.database!='f01_test_acceptance':
        raise RuntimeError('DISPOSABLE_DATABASE_REQUIRED')
    database=Database(database_url)
    try:
        with database.session(snapshot=True) as session:
            records=[RuntimeRecord(name,project,run) for name,project,run in session.execute(select(ExecutionJob.container_name,ExecutionJob.project_id,ExecutionJob.run_id).where(ExecutionJob.container_name.is_not(None))) if name is not None]
            for model in (IsolatedPreview,ArtifactPreparation):
                records.extend(RuntimeRecord(name,project,run) for name,project,run in session.execute(select(model.container_name,model.project_id,ProjectVersion.run_id).join(ProjectVersion,(ProjectVersion.id==model.version_id)&(ProjectVersion.project_id==model.project_id)).where(model.container_name.is_not(None))) if name is not None)
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=socket),base_url='http://docker',trust_env=False,timeout=30) as engine:
            return await remove_recorded(DockerSandbox(engine,image),records)
    finally:database.close()
