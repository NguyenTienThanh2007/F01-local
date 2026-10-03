"""Standalone leased worker; API processes never receive the Docker socket."""
import asyncio
import json
from datetime import timedelta
from uuid import UUID, uuid4
import httpx
from sqlalchemy import func, select
from f01.application import execution as service
from f01.application.identity import digest
from f01.application.planning import lock_owner
from f01.application.source_artifacts import apply_proposal
from f01.config import Settings, get_settings
from f01.db.models import ExecutionJob, IsolatedPreview, PlanningAttempt, SourceCandidate, VerificationEvidence
from f01.db.session import Database
from f01.domain.errors import ApplicationError
from f01.domain.execution import CommandEvidence
from f01.domain.source import GenerationContext, GenerationResult, SourceArtifact
from f01.execution.docker import DockerSandbox, SandboxError
from f01.execution.sandbox import CommandPhase
from f01.providers.base import ProviderError
from f01.providers.source import SourceGenerationProvider


class BuildWorker:
    def __init__(self, database: Database, settings: Settings, sandbox: DockerSandbox, provider: SourceGenerationProvider) -> None:
        self.database, self.settings, self.sandbox, self.provider = database, settings, sandbox, provider

    async def alive(self, identifier: UUID, token: UUID) -> bool:
        return await asyncio.to_thread(service.heartbeat, self.database, self.settings, identifier, token)

    def reserve_generation(self, identifier: UUID, token: UUID, context: GenerationContext) -> UUID:
        with self.database.session() as lookup:
            owner = lookup.scalar(select(ExecutionJob.user_id).where(ExecutionJob.id == identifier))
        assert owner is not None
        with self.database.session() as session, session.begin():
            lock_owner(session, owner)
            project, job, run = service.job_lock(session, identifier)
            service.validate_lease(session, self.settings, project, job, token)
            service.reject_secrets(self.settings, context.model_dump_json())
            estimate = len(context.model_dump_json().encode()) + 12000 + self.settings.source_output_tokens
            if estimate + job.reserved_tokens > self.settings.source_run_token_budget: raise ApplicationError("SOURCE_BUDGET_EXCEEDED")
            for old in session.scalars(select(PlanningAttempt).where(PlanningAttempt.user_id==owner,PlanningAttempt.status=="pending",PlanningAttempt.deadline_at<=service.now())):
                old.status,old.finished_at,old.error_code="abandoned",service.now(),"PLANNING_ABANDONED"
            session.flush()
            if session.scalar(select(PlanningAttempt.id).where(PlanningAttempt.user_id==owner,PlanningAttempt.status=="pending").limit(1)):raise ApplicationError("PLANNING_IN_PROGRESS")
            day = service.now().replace(hour=0, minute=0, second=0, microsecond=0)
            count, total = session.execute(select(func.count(),func.coalesce(func.sum(PlanningAttempt.reserved_tokens),0)).where(PlanningAttempt.user_id == owner,PlanningAttempt.created_at >= day)).one()
            minute = session.scalar(select(func.count()).select_from(PlanningAttempt).where(PlanningAttempt.user_id == owner,PlanningAttempt.created_at >= service.now()-timedelta(minutes=1))) or 0
            if count >= self.settings.planning_requests_per_day or minute >= self.settings.planning_requests_per_minute: raise ApplicationError("PLANNING_RATE_LIMITED")
            if estimate+total > self.settings.planning_daily_token_budget: raise ApplicationError("PLANNING_BUDGET_EXCEEDED")
            identifier = uuid4()
            session.add(PlanningAttempt(id=identifier,user_id=owner,project_id=project.id,key=f"source:{job.id}:{job.epoch}:{job.repairs}",request_hash=digest(context.model_dump_json()),status="pending",context={"kind":"source","job_id":str(job.id),"repair":job.repairs},reserved_tokens=estimate,created_at=service.now(),deadline_at=service.now()+timedelta(seconds=self.settings.planning_timeout_seconds+15)))
            job.phase = "generation_pending"
            job.reserved_tokens += estimate
            latest=session.scalar(select(SourceCandidate).where(SourceCandidate.job_id==job.id).order_by(SourceCandidate.attempt.desc()).limit(1))
            issue=json.loads(context.repair_evidence[0])["phase"] if context.repair_evidence else None
            service.emit(session,project,run,"generation" if not context.repair_evidence else "repair_attempt",provenance="model_proposed",resolves=f"{latest.id}:{issue}" if latest and issue else None)
            return identifier

    def finish_usage(self, identifier: UUID, result: GenerationResult | None, successful: bool) -> None:
        with self.database.session() as session, session.begin():
            row = session.get(PlanningAttempt,identifier,with_for_update=True)
            assert row is not None
            row.status,row.finished_at = ("succeeded" if successful else "failed"),service.now()
            if result: row.input_tokens,row.output_tokens=result.input_tokens,result.output_tokens

    async def generate(self, identifier: UUID, token: UUID, context: GenerationContext) -> SourceArtifact:
        usage = await asyncio.to_thread(self.reserve_generation,identifier,token,context)
        result: GenerationResult | None = None
        successful=False
        task = asyncio.create_task(self.provider.propose_source(context,self.settings.source_output_tokens))
        try:
            async with asyncio.timeout(self.settings.planning_timeout_seconds):
                while not task.done():
                    if not await self.alive(identifier,token): raise ApplicationError("BUILD_CANCELED_OR_LEASE_LOST")
                    await asyncio.wait({task},timeout=0.25)
                result = GenerationResult.model_validate_json((await task).model_dump_json())
            if result.output_tokens is not None and result.output_tokens>self.settings.source_output_tokens or result.input_tokens is not None and result.input_tokens>131072: raise ApplicationError("SOURCE_BUDGET_EXCEEDED")
            service.reject_secrets(self.settings,result.model_dump_json())
            artifact=apply_proposal(result.proposal,context.lineage,base=context.base_source,forbidden_secrets=service.forbidden(self.settings),candidate_base=bool(context.repair_evidence))
            successful=True
            return artifact
        finally:
            if not task.done():
                task.cancel(); await asyncio.gather(task,return_exceptions=True)
            await asyncio.to_thread(self.finish_usage,usage,result,successful)

    def save_candidate(self, identifier: UUID, token: UUID, source: SourceArtifact) -> UUID:
        with self.database.session() as session, session.begin():
            project,job,run=service.job_lock(session,identifier)
            service.validate_lease(session,self.settings,project,job,token)
            context=GenerationContext.model_validate_json(json.dumps(job.context))
            if source.lineage != context.lineage: raise ApplicationError("STALE_RUN_CONTEXT")
            service.reject_secrets(self.settings,source.model_dump_json())
            attempt=(session.scalar(select(func.max(SourceCandidate.attempt)).where(SourceCandidate.job_id==job.id)) or 0)+1
            candidate=SourceCandidate(id=uuid4(),project_id=project.id,job_id=job.id,attempt=attempt,digest=source.digest,parent_digest=source.parent_digest,source=source.model_dump(mode="json"),created_at=service.now())
            session.add(candidate);job.phase="generated"
            service.emit(session,project,run,"generated",candidate=candidate.id,provenance="generated")
            return candidate.id

    def bind_container(self, identifier: UUID, token: UUID, candidate: UUID) -> tuple[str, str]:
        with self.database.session() as session, session.begin():
            project,job,run=service.job_lock(session,identifier)
            service.validate_lease(session,self.settings,project,job,token)
            row=session.get(SourceCandidate,candidate);assert row is not None
            name=self.sandbox.name(job.id,job.epoch,row.attempt)
            import secrets
            job.container_name=name
            job.preview_id,job.preview_key=uuid4(),secrets.token_urlsafe(32)
            # Persist identity BEFORE an external create, so interrupted creates are recoverable.
            return name,f"/p/{job.preview_id}/{job.preview_key}"

    def record(self, identifier: UUID, token: UUID, candidate: UUID, evidence: CommandEvidence) -> None:
        with self.database.session() as session, session.begin():
            project,job,run=service.job_lock(session,identifier)
            service.validate_lease(session,self.settings,project,job,token)
            service.reject_secrets(self.settings,evidence.model_dump_json())
            row=VerificationEvidence(id=uuid4(),project_id=project.id,candidate_id=candidate,phase=evidence.phase,content=evidence.model_dump(mode="json"),created_at=service.now())
            session.add(row);job.phase=evidence.phase
            run.phase="verifying" if evidence.phase in ("typecheck","build","test","verification") else "building"
            project.lifecycle=run.phase
            project.status_event_sequence=service.emit(session,project,run,evidence.phase,candidate=candidate,evidence=row.id,failed=evidence.exit_code!=0,
                issue=f"{candidate}:{evidence.phase}" if evidence.exit_code else None)

    def prepare_repair(self, identifier: UUID, token: UUID, source: SourceArtifact, issue: CommandEvidence) -> GenerationContext:
        with self.database.session() as session, session.begin():
            project,job,run=service.job_lock(session,identifier)
            service.validate_lease(session,self.settings,project,job,token)
            if job.repairs>=self.settings.repair_attempts: raise ApplicationError("REPAIR_EXHAUSTED")
            if issue.phase not in ("typecheck","build","test"): raise ApplicationError("VERIFICATION_FAILED")
            job.repairs+=1
            service.emit(session,project,run,"issue_detection",failed=True)
            context=GenerationContext.model_validate_json(json.dumps(job.context))
            # Evidence has codes, validated paths and line numbers, never unrestricted logs.
            value=context.model_copy(update={"base_source":source,"repair_evidence":(issue.model_dump_json(exclude={"argv"}),)})
            return GenerationContext.model_validate_json(value.model_dump_json())

    def initial(self, identifier: UUID) -> tuple[GenerationContext, SourceArtifact | None]:
        with self.database.session() as session:
            job=session.get(ExecutionJob,identifier);assert job is not None
            context=GenerationContext.model_validate_json(json.dumps(job.context))
            prior=session.scalar(select(SourceCandidate).where(SourceCandidate.job_id==identifier).order_by(SourceCandidate.attempt.desc()).limit(1))
            return context,SourceArtifact.model_validate_json(json.dumps(prior.source)) if prior else None

    async def execute(self, identifier: UUID, token: UUID) -> None:
        retained=False
        name: str | None = None
        try:
            await self.sandbox.ready()
            context,source=await asyncio.to_thread(self.initial,identifier)
            source=source or await self.generate(identifier,token,context)
            while True:
                candidate=await asyncio.to_thread(self.save_candidate,identifier,token,source)
                name,preview_path=await asyncio.to_thread(self.bind_container,identifier,token,candidate)
                assert name is not None
                alive=lambda:self.alive(identifier,token)
                await self.sandbox.create(name,source.lineage.project_id,await asyncio.to_thread(self.run_id,identifier),preview_path)
                evidence=await self.sandbox.materialize(name,source,alive)
                await asyncio.to_thread(self.record,identifier,token,candidate,evidence)
                if evidence.exit_code: raise ApplicationError("MATERIALIZATION_FAILED")
                tests=tuple(f.path for f in source.files if f.path.startswith("tests/"))
                phases=[CommandPhase.INSTALL,CommandPhase.TYPECHECK,CommandPhase.BUILD]+([CommandPhase.TEST] if tests else [])
                failed: CommandEvidence | None = None
                for phase in phases:
                    evidence=await self.sandbox.command(name,phase,tests,alive)
                    await asyncio.to_thread(self.record,identifier,token,candidate,evidence)
                    if evidence.exit_code: failed=evidence;break
                if failed:
                    await self.sandbox.remove(name);name=None
                    repair=await asyncio.to_thread(self.prepare_repair,identifier,token,source,failed)
                    source=await self.generate(identifier,token,repair)
                    continue
                evidence=await self.sandbox.start_preview(name,source,alive,preview_path)
                await asyncio.to_thread(self.record,identifier,token,candidate,evidence)
                if evidence.exit_code: raise ApplicationError("VERIFICATION_FAILED")
                retained=await asyncio.to_thread(service.publish,self.database,self.settings,identifier,token,candidate)
                return
        except (ApplicationError,SandboxError,ProviderError) as error:
            code=error.code.value if isinstance(error,ProviderError) else error.code
            await asyncio.to_thread(service.fail,self.database,identifier,token,code)
        except (TimeoutError,asyncio.CancelledError):
            await asyncio.to_thread(service.fail,self.database,identifier,token,"BUILD_TIMEOUT")
        except Exception:
            await asyncio.to_thread(service.fail,self.database,identifier,token,"EXECUTION_FAILED")
        finally:
            if name and not retained:
                # A commit may have succeeded while its caller was interrupted. Reconcile before teardown.
                try: retained=await asyncio.to_thread(self.published,name)
                except Exception: retained=True  # retain bounded runtime until durable recovery can reconcile
            if name and not retained:
                try:
                    await asyncio.shield(self.sandbox.remove(name))
                    await asyncio.to_thread(self.clear_container,identifier,name)
                except Exception:
                    # Persisted identity is deliberately retained for recovery; no false cleanup claim.
                    pass

    def published(self, name: str) -> bool:
        with self.database.session() as session:
            return session.scalar(select(IsolatedPreview.id).where(IsolatedPreview.container_name==name)) is not None

    def run_id(self, identifier: UUID) -> UUID:
        with self.database.session() as session:
            job=session.get(ExecutionJob,identifier);assert job is not None
            return job.run_id

    def clear_container(self, identifier: UUID, name: str) -> None:
        with self.database.session() as session, session.begin():
            _,job,_=service.job_lock(session,identifier)
            if job.container_name==name:job.container_name=None

    async def recover(self) -> None:
        with self.database.session() as session:
            rows=session.scalars(select(ExecutionJob).where((ExecutionJob.state=="leased") & (ExecutionJob.lease_until<=service.now()) | (ExecutionJob.state=="done") & ExecutionJob.container_name.is_not(None))).all()
        for row in rows:
            if row.container_name:
                try:await self.sandbox.remove(row.container_name)
                except SandboxError:continue
            with self.database.session() as session,session.begin():
                project,job,run=service.job_lock(session,row.id)
                if job.state=="done":job.container_name=None;continue
                if job.lease_until and job.lease_until>service.now():continue
                job.container_name=None
                if job.phase=="generation_pending":service.terminal(session,project,job,run,"PROVIDER_OUTCOME_UNKNOWN")
                else:
                    job.state,job.lease_token,job.lease_until,job.phase="queued",None,None,"recovery"
                    service.emit(session,project,run,"restart_recovery")
        with self.database.session() as session:
            previews=session.scalars(select(IsolatedPreview).where(IsolatedPreview.state.in_(["ready","expired","cleanup_pending"]),IsolatedPreview.expires_at<=service.now())).all()
        for preview in previews:
            with self.database.session() as session,session.begin():
                saved=session.get(IsolatedPreview,preview.id,with_for_update=True);assert saved is not None
                saved.state="cleanup_pending"
            try:await self.sandbox.remove(preview.container_name)
            except SandboxError:continue
            with self.database.session() as session,session.begin():
                saved=session.get(IsolatedPreview,preview.id,with_for_update=True);assert saved is not None
                saved.state="removed"

    async def run_once(self) -> bool:
        await self.recover()
        claimed=await asyncio.to_thread(service.claim,self.database,self.settings)
        if not claimed:return False
        await self.execute(*claimed)
        return True


async def main() -> None:
    from f01.providers.factory import source_provider
    settings=get_settings()
    if not settings.real_execution_enabled:raise SystemExit("EXECUTION_UNAVAILABLE")
    database=Database(settings.database_url)
    try:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket),base_url="http://docker",trust_env=False,timeout=180) as engine, httpx.AsyncClient(trust_env=False,timeout=settings.planning_timeout_seconds) as models:
            worker=BuildWorker(database,settings,DockerSandbox(engine,settings.sandbox_image_id,settings.build_timeout_seconds+settings.preview_ttl_seconds),source_provider(settings,models))
            async def loop() -> None:
                while True:
                    if not await worker.run_once():await asyncio.sleep(1)
            await asyncio.gather(*(loop() for _ in range(settings.build_concurrency)))
    finally:database.close()

if __name__=="__main__":asyncio.run(main())
