"""Bounded static Build Output API data validation; never extracts or runs output."""
import base64
import hashlib
import json
import re
from dataclasses import dataclass
from f01.domain.errors import ApplicationError

MAX_BYTES = 16 * 1024 * 1024
MAX_FILES = 2000
OUTPUT_CONFIG = {'version': 3, 'routes': [{'handle': 'filesystem'}]}


@dataclass(frozen=True)
class PackageFile:
    path: str
    data: bytes
    sha256: str


def package_digest(files: list[PackageFile]) -> str:
    manifest = [{'path': f.path, 'sha256': f.sha256, 'bytes': len(f.data)} for f in sorted(files, key=lambda f: f.path)]
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_package(value: dict[str, object], expected_digest: str | None = None) -> list[PackageFile]:
    try:
        if set(value) != {'files'}:
            raise ValueError()
        raw = value['files']
        if not isinstance(raw, list) or not 2 <= len(raw) <= MAX_FILES:
            raise ValueError()
        files: list[PackageFile] = []
        paths: set[str] = set()
        size = 0
        for item in raw:
            if not isinstance(item, dict) or set(item) != {'path', 'data', 'sha256'}:
                raise ValueError()
            path, data, sha = item['path'], item['data'], item['sha256']
            if not isinstance(path, str) or not isinstance(data, str) or not isinstance(sha, str):
                raise ValueError()
            if len(path) > 500 or path in paths or path.casefold() in paths:
                raise ValueError()
            if path != '.vercel/output/config.json':
                if not path.startswith('.vercel/output/static/'):
                    raise ValueError()
                relative = path.removeprefix('.vercel/output/static/')
                if not re.fullmatch(r'[A-Za-z0-9_@./()-]+', relative) or any(p in ('', '.', '..') or p.startswith('.') for p in relative.split('/')):
                    raise ValueError()
            if len(data) > MAX_BYTES * 4 // 3 + 4:
                raise ValueError()
            binary = base64.b64decode(data, validate=True)
            size += len(binary)
            if size > MAX_BYTES or hashlib.sha256(binary).hexdigest() != sha:
                raise ValueError()
            paths.update((path, path.casefold()))
            files.append(PackageFile(path, binary, sha))
        by_path = {f.path: f for f in files}
        if json.loads(by_path['.vercel/output/config.json'].data) != OUTPUT_CONFIG or '.vercel/output/static/index.html' not in by_path or '.vercel/output/static/__f01_release.json' not in by_path:
            raise ValueError()
        if expected_digest is not None and package_digest(files) != expected_digest:
            raise ValueError()
        return files
    except (ValueError, TypeError, KeyError):
        raise ApplicationError('RELEASE_PACKAGE_INVALID') from None
