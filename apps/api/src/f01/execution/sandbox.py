"""Fail-closed Docker policy and prerequisite probe, not an operational executor.

There is deliberately no create/start/exec method: real isolation, cleanup,
cancellation and preview tests require a Docker-capable environment first.
"""
import asyncio
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

import httpx

from f01.domain.source import validate_source_path

API_VERSION = "v1.47"


class CommandPhase(StrEnum):
    INSTALL = "install"
    TYPECHECK = "typecheck"
    BUILD = "build"
    TEST = "test"


@dataclass(frozen=True)
class CommandPolicy:
    argv: tuple[str, ...]
    working_directory: Literal["/work"]
    timeout_seconds: int


def command_policy(phase: CommandPhase, test_paths: tuple[str, ...] = ()) -> CommandPolicy:
    """No shell, user argv, mutable package scripts, globs, or model commands."""
    if not isinstance(phase, CommandPhase):
        raise ValueError("Unknown application-owned command phase.")
    if phase != CommandPhase.TEST and test_paths:
        raise ValueError("Unexpected command input.")
    if phase == CommandPhase.INSTALL:
        return CommandPolicy(("/usr/local/bin/pnpm", "install", "--offline", "--frozen-lockfile", "--ignore-scripts"), "/work", 90)
    if phase == CommandPhase.TYPECHECK:
        return CommandPolicy(("/usr/local/bin/node", "/opt/f01/node_modules/typescript/bin/tsc", "--noEmit"), "/work", 60)
    if phase == CommandPhase.BUILD:
        return CommandPolicy(("/usr/local/bin/node", "/opt/f01/node_modules/next/dist/bin/next", "build", "--webpack"), "/work", 120)
    if not test_paths or len(test_paths) > 16 or len(set(test_paths)) != len(test_paths):
        raise ValueError("Tests require explicit bounded paths.")
    for path in test_paths:
        validate_source_path(path)
        if not path.startswith("tests/"):
            raise ValueError("Invalid generated test path.")
    return CommandPolicy(("/usr/local/bin/node", "--test", "--", *sorted(test_paths)), "/work", 30)


@dataclass(frozen=True)
class SandboxLimits:
    memory_bytes: int = 2147483648
    cpus: int = 2
    processes: int = 128
    workspace_bytes: int = 1073741824
    temporary_bytes: int = 134217728

    def __post_init__(self) -> None:
        if any(type(x) is not int for x in (self.memory_bytes, self.cpus, self.processes, self.workspace_bytes, self.temporary_bytes)):
            raise ValueError("Sandbox limits must be integers.")
        if not (268435456 <= self.memory_bytes <= 2147483648 and 1 <= self.cpus <= 2
                and 16 <= self.processes <= 128 and 16777216 <= self.workspace_bytes <= 1073741824
                and 16777216 <= self.temporary_bytes <= 134217728):
            raise ValueError("Sandbox limits exceed the policy.")


def validate_image_id(image: str) -> str:
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise ValueError("Sandbox image must use an exact local content ID.")
    return image


def container_policy(image: str, project_id: UUID, run_id: UUID, limits: SandboxLimits = SandboxLimits()) -> dict[str, object]:
    """Pure proposed Engine specification. Constructing it is not isolation evidence."""
    validate_image_id(image)
    return {
        "Image": image, "User": "10000:10000", "WorkingDir": "/work",
        "Entrypoint": ["/usr/local/bin/node"], "Cmd": ["/opt/f01/idle.mjs"],
        "Env": ["HOME=/tmp", "PATH=/usr/local/bin:/usr/bin:/bin", "NODE_ENV=production",
                "NEXT_TELEMETRY_DISABLED=1", "CI=1"],
        "NetworkDisabled": True, "OpenStdin": False, "Tty": False,
        "Labels": {"f01.role": "candidate", "f01.project_id": str(project_id), "f01.run_id": str(run_id)},
        "HostConfig": {
            "Privileged": False, "ReadonlyRootfs": True, "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"], "NetworkMode": "none",
            "PidMode": "", "IpcMode": "private", "CgroupnsMode": "private",
            "Memory": limits.memory_bytes, "MemorySwap": limits.memory_bytes,
            "NanoCpus": limits.cpus * 1000000000, "PidsLimit": limits.processes,
            "Tmpfs": {
                "/work": f"rw,noexec,nosuid,nodev,size={limits.workspace_bytes},mode=0700,uid=10000,gid=10000",
                "/tmp": f"rw,noexec,nosuid,nodev,size={limits.temporary_bytes},mode=0700,uid=10000,gid=10000",
            },
            "Binds": [], "Mounts": [], "Devices": [], "DeviceRequests": [], "PortBindings": {},
            "PublishAllPorts": False, "RestartPolicy": {"Name": "no"}, "AutoRemove": False,
            "Ulimits": [{"Name": "nofile", "Soft": 1024, "Hard": 1024}, {"Name": "core", "Soft": 0, "Hard": 0}],
            "LogConfig": {"Type": "local", "Config": {"max-size": "1m", "max-file": "1"}},
        },
    }


@dataclass(frozen=True)
class SandboxPrerequisites:
    status: Literal["unavailable", "unsupported", "prerequisites_present"]
    code: str
    # Even a passing daemon probe cannot certify resource enforcement or isolation.
    execution_enabled: Literal[False] = False


class SandboxBoundary(Protocol):
    async def prerequisites(self, image: str) -> SandboxPrerequisites: ...


def daemon_supports_policy(info: object) -> bool:
    if not isinstance(info, dict):
        return False
    options = info.get("SecurityOptions")
    return (
        info.get("OSType") == "linux" and info.get("CgroupVersion") == "2"
        and all(info.get(key) is True for key in ("MemoryLimit", "SwapLimit", "CpuCfsPeriod", "CpuCfsQuota", "PidsLimit"))
        and isinstance(options, list) and any(isinstance(v, str) and v.startswith("name=seccomp,profile=") and "unconfined" not in v for v in options)
    )


class DockerPrerequisiteProbe:
    """Read-only Engine probe. Use a private worker-owned Unix socket, not the main API."""
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def _get(self, path: str) -> object:
        async with self._client.stream("GET", f"/{API_VERSION}{path}", follow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError("Engine prerequisite unavailable.")
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                if len(raw) + len(chunk) > 131072:
                    raise ValueError("Invalid Engine prerequisite response.")
                raw.extend(chunk)
        return httpx.Response(200, content=bytes(raw)).json()

    async def prerequisites(self, image: str) -> SandboxPrerequisites:
        validate_image_id(image)
        try:
            async with asyncio.timeout(5):
                info = await self._get("/info")
                if not daemon_supports_policy(info):
                    return SandboxPrerequisites("unsupported", "SANDBOX_POLICY_UNSUPPORTED")
                installed = await self._get(f"/images/{image}/json")
            if not isinstance(installed, dict) or installed.get("Id") != image or installed.get("Os") != "linux":
                return SandboxPrerequisites("unsupported", "SANDBOX_IMAGE_INVALID")
            config = installed.get("Config")
            if not isinstance(config, dict) or config.get("User") != "10000:10000":
                return SandboxPrerequisites("unsupported", "SANDBOX_IMAGE_INVALID")
            labels = config.get("Labels")
            if not isinstance(labels, dict) or labels.get("f01.recipe") != "next-web-v1":
                return SandboxPrerequisites("unsupported", "SANDBOX_IMAGE_INVALID")
            # Image volumes could introduce persistent anonymous storage outside disk policy.
            if config.get("Volumes") or config.get("OnBuild"):
                return SandboxPrerequisites("unsupported", "SANDBOX_IMAGE_INVALID")
            return SandboxPrerequisites("prerequisites_present", "ISOLATION_VERIFICATION_REQUIRED")
        except Exception:
            return SandboxPrerequisites("unavailable", "SANDBOX_ENGINE_UNAVAILABLE")
