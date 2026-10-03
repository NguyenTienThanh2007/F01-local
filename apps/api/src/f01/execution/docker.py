"""Private-worker Docker adapter. Generated code never executes on the factory host."""
import asyncio
import base64
import json
import re
from collections.abc import Awaitable, Callable
from uuid import UUID
import httpx
from f01.application.source_artifacts import validate_artifact
from f01.domain.execution import CommandEvidence
from f01.domain.source import SourceArtifact, validate_source_path
from f01.execution.sandbox import API_VERSION, CommandPhase, DockerPrerequisiteProbe, command_policy, container_policy, SandboxLimits

class SandboxError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

class DockerSandbox:
    def __init__(self, client: httpx.AsyncClient, image: str, lifetime_seconds: int = 4200, limits: SandboxLimits = SandboxLimits()) -> None:
        self.client, self.image = client, image
        if not 60 <= lifetime_seconds <= 87600: raise ValueError("Invalid runtime lifetime.")
        self.lifetime_seconds = lifetime_seconds
        self.limits = limits

    async def request(self, method: str, path: str, body: object = None, *, limit: int = 131072, missing_ok: bool = False) -> bytes:
        try:
            async with self.client.stream(method, f"/{API_VERSION}{path}", json=body if body is not None else None) as response:
                if missing_ok and response.status_code == 404: return b""
                if not 200 <= response.status_code < 300: raise SandboxError("SANDBOX_ENGINE_ERROR")
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(raw)+len(chunk)>limit: raise SandboxError("SANDBOX_OUTPUT_LIMIT")
                    raw.extend(chunk)
                return bytes(raw)
        except httpx.HTTPError:
            raise SandboxError("SANDBOX_ENGINE_UNAVAILABLE") from None

    async def ready(self) -> None:
        result = await DockerPrerequisiteProbe(self.client).prerequisites(self.image)
        if result.status != "prerequisites_present": raise SandboxError(result.code)

    @staticmethod
    def name(job: UUID, epoch: int, attempt: int) -> str:
        return f"f01-{job.hex}-{epoch}-{attempt}"

    async def create(self, name: str, project: UUID, run: UUID, preview_path: str) -> None:
        if not re.fullmatch(r"f01-[a-f0-9]{32}-[0-9]+-[0-9]+", name): raise SandboxError("SANDBOX_ID_INVALID")
        if not re.fullmatch(r"/p/[a-f0-9-]{36}/[A-Za-z0-9_-]{43}", preview_path): raise SandboxError("PREVIEW_PATH_INVALID")
        specification = container_policy(self.image, project, run, self.limits)
        environment = specification["Env"]
        assert isinstance(environment,list)
        environment.extend(["F01_PREVIEW_PATH="+preview_path, "F01_LIFETIME_SECONDS="+str(self.lifetime_seconds)])
        await self.request("POST", f"/containers/create?name={name}", specification)
        await self.request("POST", f"/containers/{name}/start")

    async def remove(self, name: str) -> None:
        if not re.fullmatch(r"f01-[a-f0-9]{32}-[0-9]+-[0-9]+", name): raise SandboxError("SANDBOX_ID_INVALID")
        await self.request("DELETE", f"/containers/{name}?force=true&v=true", missing_ok=True)

    async def exec(self, name: str, argv: tuple[str, ...], seconds: float, alive: Callable[[], Awaitable[bool]], *, limit: int = 8192) -> bytes:
        # Only this adapter's application-owned callers select argv. No public/model argv input.
        specification = {"Cmd": list(argv), "User": "10000:10000", "WorkingDir": "/work", "AttachStdout": True, "AttachStderr": False, "Tty": False, "Privileged": False}
        identifier = json.loads(await self.request("POST", f"/containers/{name}/exec", specification))["Id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{64}", identifier): raise SandboxError("SANDBOX_ENGINE_ERROR")
        async def output() -> bytes:
            raw = await self.request("POST", f"/exec/{identifier}/start", {"Detach": False, "Tty": False}, limit=limit+4096)
            # Docker multiplexed non-TTY stream. No raw stderr/logs returned to the application.
            result = bytearray()
            while raw:
                if len(raw)<8 or raw[0] not in (1,2) or raw[1:4]!=b"\0\0\0": raise SandboxError("SANDBOX_STREAM_INVALID")
                size = int.from_bytes(raw[4:8], "big")
                if size>len(raw)-8: raise SandboxError("SANDBOX_STREAM_INVALID")
                if raw[0] == 1: result.extend(raw[8:8+size])
                raw = raw[8+size:]
            if len(result)>limit: raise SandboxError("SANDBOX_OUTPUT_LIMIT")
            state = json.loads(await self.request("GET", f"/exec/{identifier}/json"))
            if state.get("Running") or state.get("ExitCode") != 0: raise SandboxError("SANDBOX_HELPER_FAILED")
            return bytes(result)
        task = asyncio.create_task(output())
        try:
            async with asyncio.timeout(seconds):
                while not task.done():
                    if not await alive(): raise SandboxError("BUILD_CANCELED_OR_LEASE_LOST")
                    await asyncio.wait({task}, timeout=0.25)
                return await task
        except TimeoutError:
            raise SandboxError("SANDBOX_TIMEOUT") from None
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    @staticmethod
    def source_argument(source: SourceArtifact) -> str:
        validate_artifact(source)
        return base64.b64encode(source.model_dump_json().encode()).decode()

    async def evidence(self, name: str, phase: str, argv: tuple[str, ...], seconds: int, alive: Callable[[], Awaitable[bool]]) -> CommandEvidence:
        raw = await self.exec(name, argv, seconds, alive)
        try:
            payload = json.loads(raw)
            evidence = CommandEvidence.model_validate({**payload, "phase": phase, "argv": list(argv[:2]), "image_id": self.image})
            # Remove raw arguments carrying source. Never persist model content as command metadata.
            for issue in evidence.diagnostics:
                if issue.path: validate_source_path(issue.path)
            return evidence
        except (ValueError, TypeError): raise SandboxError("SANDBOX_EVIDENCE_INVALID") from None

    async def materialize(self, name: str, source: SourceArtifact, alive: Callable[[], Awaitable[bool]]) -> CommandEvidence:
        return await self.evidence(name, "materialization", ("/usr/local/bin/node", "/opt/f01/materialize.mjs", self.source_argument(source)), 15, alive)

    async def command(self, name: str, phase: CommandPhase, tests: tuple[str, ...], alive: Callable[[], Awaitable[bool]]) -> CommandEvidence:
        policy = command_policy(phase, tests if phase == CommandPhase.TEST else ())
        evidence = await self.evidence(name, phase.value, ("/usr/local/bin/node", "/opt/f01/command.mjs", phase.value, *policy.argv), policy.timeout_seconds, alive)
        return evidence.model_copy(update={"argv": list(policy.argv)})

    async def start_preview(self, name: str, source: SourceArtifact, alive: Callable[[], Awaitable[bool]], preview_path: str) -> CommandEvidence:
        result = await self.evidence(name, "verification", ("/usr/local/bin/node", "/opt/f01/verify.mjs", self.source_argument(source)), 15, alive)
        if result.exit_code: return result
        await self.exec(name, ("/usr/local/bin/node", "/opt/f01/serve.mjs"), 10, alive)
        for _ in range(40):
            if not await alive(): raise SandboxError("BUILD_CANCELED_OR_LEASE_LOST")
            try:
                response = await self.fetch(name, preview_path+"/", alive)
                if response[0] == 200: return result
            except SandboxError: pass
            await asyncio.sleep(0.25)
        raise SandboxError("PREVIEW_HEALTH_FAILED")

    async def fetch(self, name: str, path: str, alive: Callable[[], Awaitable[bool]]) -> tuple[int, str, bytes]:
        if not path.startswith("/") or path.startswith("//") or "\\" in path or len(path)>2048: raise SandboxError("PREVIEW_PATH_INVALID")
        raw = await self.exec(name, ("/usr/local/bin/node", "/opt/f01/fetch.mjs", path), 10, alive, limit=3000000)
        try:
            response = json.loads(raw)
            body = base64.b64decode(response["body"], validate=True)
            status, kind = response["status"], response["type"]
            if type(status) is not int or not 100 <= status <= 599 or not isinstance(kind, str) or len(kind)>100 or "\r" in kind or "\n" in kind or len(body)>2097152: raise ValueError()
            return status, kind, body
        except (ValueError, KeyError, TypeError): raise SandboxError("PREVIEW_RESPONSE_INVALID") from None
