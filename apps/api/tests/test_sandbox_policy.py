import asyncio
import json
from dataclasses import replace
from uuid import UUID

import httpx
import pytest

from f01.execution.sandbox import CommandPhase, DockerPrerequisiteProbe, SandboxLimits, command_policy, container_policy, daemon_supports_policy

IMAGE = "sha256:" + "a" * 64


def engine_info() -> dict[str, object]:
    return {"OSType": "linux", "CgroupVersion": "2", "MemoryLimit": True, "SwapLimit": True,
            "CpuCfsPeriod": True, "CpuCfsQuota": True, "PidsLimit": True, "SecurityOptions": ["name=seccomp,profile=builtin"]}


def test_proposed_policy_is_bounded_private_nonroot_and_secret_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-factory-secret")
    monkeypatch.setenv("DATABASE_URL", "synthetic-private-database")
    policy = container_policy(IMAGE, UUID(int=1), UUID(int=2))
    host = policy["HostConfig"]
    assert isinstance(host, dict)
    assert policy["User"] == "10000:10000" and policy["NetworkDisabled"] is True
    assert host["ReadonlyRootfs"] is True and host["Privileged"] is False and host["CapDrop"] == ["ALL"]
    assert host["NetworkMode"] == "none" and host["CgroupnsMode"] == "private" and host["IpcMode"] == "private"
    assert host["Binds"] == [] and host["Mounts"] == [] and host["Devices"] == [] and host["PortBindings"] == {}
    assert host["Memory"] == host["MemorySwap"] == 2147483648
    assert host["NanoCpus"] == 2000000000 and host["PidsLimit"] == 128
    work = host["Tmpfs"]
    assert isinstance(work, dict) and "size=1073741824" in work["/work"]
    assert "synthetic-factory-secret" not in json.dumps(policy) and "synthetic-private-database" not in json.dumps(policy)
    assert "docker.sock" not in json.dumps(policy)


@pytest.mark.parametrize("image", ["node:latest", "node:24", "sha256:abc", "sha256:" + "A" * 64, "sha256:" + "a" * 64 + "/escape"])
def test_mutable_or_invalid_images_rejected(image: str) -> None:
    with pytest.raises(ValueError):
        container_policy(image, UUID(int=1), UUID(int=2))


@pytest.mark.parametrize("change", [{"memory_bytes": 0}, {"memory_bytes": 4294967296}, {"processes": 0}, {"cpus": 3}, {"cpus": True}, {"workspace_bytes": 2147483648}, {"temporary_bytes": 0}])
def test_resource_limits_cannot_be_unbounded(change: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        replace(SandboxLimits(), **change)


def test_commands_are_owned_and_tests_use_explicit_validated_paths() -> None:
    install = command_policy(CommandPhase.INSTALL)
    assert "--ignore-scripts" in install.argv and "--offline" in install.argv and "--frozen-lockfile" in install.argv
    assert "--prod=false" in install.argv  # NODE_ENV=production must retain trusted type dependencies.
    for phase in (CommandPhase.TYPECHECK, CommandPhase.BUILD):
        command = command_policy(phase)
        assert command.working_directory == "/work" and 0 < command.timeout_seconds <= 120
        assert "sh" not in command.argv and "run" not in command.argv
    command = command_policy(CommandPhase.TEST, ("tests/b.test.mjs", "tests/a.test.mjs"))
    assert command.argv[-2:] == ("tests/a.test.mjs", "tests/b.test.mjs")
    for paths in ((), ("tests/../../escape.test.mjs",), ("tests/test;echo.test.mjs",), ("tests/$(echo).test.mjs",), ("app/test.ts",), ("tests/a.test.mjs", "tests/a.test.mjs")):
        with pytest.raises(ValueError):
            command_policy(CommandPhase.TEST, paths)
    with pytest.raises(ValueError):
        command_policy("echo injected")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        command_policy(CommandPhase.BUILD, ("tests/a.test.mjs",))


@pytest.mark.parametrize("change", [{"OSType": "windows"}, {"CgroupVersion": "1"}, {"MemoryLimit": False}, {"SwapLimit": False}, {"CpuCfsQuota": False}, {"PidsLimit": False}, {"SecurityOptions": ["name=seccomp,profile=unconfined"]}, {"SecurityOptions": []}])
def test_missing_isolation_prerequisites_fail_closed(change: dict[str, object]) -> None:
    assert not daemon_supports_policy({**engine_info(), **change})


def test_daemon_probe_is_read_only_and_does_not_enable_execution() -> None:
    calls: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        calls.append(request.url.path)
        body = engine_info() if request.url.path.endswith("/info") else {"Id": IMAGE, "Os": "linux", "Config": {"User": "10000:10000", "Labels": {"f01.recipe": "next-web-v1"}}}
        return httpx.Response(200, json=body)
    async def run() -> None:
        async with httpx.AsyncClient(base_url="http://docker", transport=httpx.MockTransport(handler)) as client:
            probe = DockerPrerequisiteProbe(client)
            result = await probe.prerequisites(IMAGE)
            assert result.status == "prerequisites_present" and result.execution_enabled is False
            assert result.code == "ISOLATION_VERIFICATION_REQUIRED"
            assert not hasattr(probe, "execute") and not hasattr(probe, "start")
    asyncio.run(run())
    assert calls == ["/v1.47/info", f"/v1.47/images/{IMAGE}/json"]


@pytest.mark.parametrize("failure", ["unavailable", "redirect", "oversize", "invalid", "privileged_image", "volume", "onbuild"])
def test_bad_daemon_or_image_never_exposes_raw_diagnostics(failure: str) -> None:
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failure == "unavailable":
            raise httpx.ConnectError("private socket diagnostic")
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "http://other.internal"})
        if failure == "oversize":
            return httpx.Response(200, content=b"x" * 131073)
        if failure == "invalid":
            return httpx.Response(200, content=b"invalid")
        if request.url.path.endswith("/info"):
            return httpx.Response(200, json=engine_info())
        config: dict[str, object] = {"User": "10000:10000", "Labels": {"f01.recipe": "next-web-v1"}}
        if failure == "privileged_image":
            config["User"] = "root"
        if failure == "volume":
            config["Volumes"] = {"/persist": {}}
        if failure == "onbuild":
            config["OnBuild"] = ["RUN malicious"]
        return httpx.Response(200, json={"Id": IMAGE, "Os": "linux", "Config": config})
    async def run() -> None:
        async with httpx.AsyncClient(base_url="http://docker", transport=httpx.MockTransport(handler)) as client:
            result = await DockerPrerequisiteProbe(client).prerequisites(IMAGE)
            assert result.status != "prerequisites_present" and result.execution_enabled is False
            assert "private" not in result.code
    asyncio.run(run())
    assert calls <= 2
