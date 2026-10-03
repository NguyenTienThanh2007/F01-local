"""Read-only sandbox prerequisites. Never runs a container or model output."""
import argparse
import asyncio
import json
from pathlib import Path
import stat

import httpx

from f01.execution.sandbox import DockerPrerequisiteProbe, SandboxPrerequisites, validate_image_id


async def check(socket: Path, image: str) -> SandboxPrerequisites:
    try:
        if not socket.is_absolute() or not stat.S_ISSOCK(socket.lstat().st_mode):
            return SandboxPrerequisites("unavailable", "SANDBOX_SOCKET_UNAVAILABLE")
    except OSError:
        return SandboxPrerequisites("unavailable", "SANDBOX_SOCKET_UNAVAILABLE")
    transport = httpx.AsyncHTTPTransport(uds=str(socket), retries=0)
    async with httpx.AsyncClient(transport=transport, base_url="http://docker", trust_env=False, timeout=5, follow_redirects=False) as client:
        return await DockerPrerequisiteProbe(client).prerequisites(image)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, default=Path("/var/run/docker.sock"))
    parser.add_argument("--image-id", required=True, type=validate_image_id)
    args = parser.parse_args()
    result = asyncio.run(check(args.socket, args.image_id))
    print(json.dumps({"status": result.status, "code": result.code, "execution_enabled": result.execution_enabled}))
    # A prerequisites check is never proof of an operational executor.
    raise SystemExit(0 if result.status == "prerequisites_present" else 1)


if __name__ == "__main__":
    main()
