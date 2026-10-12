import copy
import pytest
from f01.domain.errors import ApplicationError
from f01.release.package import validate_package, package_digest
from f01.application.releases import public_url
from tests.persistence.test_releases import package


def test_package_digest_and_exact_paths() -> None:
    value = package({'preparation_id': 'controlled'})
    digest = package_digest(validate_package(value))
    assert validate_package(value, digest)
    with pytest.raises(ApplicationError):
        validate_package(value, '0'*64)
    changed = copy.deepcopy(value)
    raw = changed['files']
    assert isinstance(raw, list)
    raw[0]['data'] = 'AAAA'
    with pytest.raises(ApplicationError):
        validate_package(changed)


@pytest.mark.parametrize('path', ['.vercel/output/static/../.env', '.vercel/output/static/.env', '.vercel/output/functions/api.func/index.js', '/etc/passwd', '.vercel/output/static/a\\b', '.vercel/output/static/a//b', '.vercel/output/static/a/./b'])
def test_untrusted_output_cannot_expand_release_authority(path: str) -> None:
    value = package({'test': 'controlled'})
    raw = value['files']
    assert isinstance(raw, list)
    raw[1]['path'] = path
    with pytest.raises(ApplicationError, match='RELEASE_PACKAGE_INVALID'):
        validate_package(value)


@pytest.mark.parametrize('url', ['http://a.vercel.app', 'https://a.vercel.app:443', 'https://a.vercel.app.evil.test', 'https://user:secret@a.vercel.app', 'https://a.vercel.app/path', 'https://a.vercel.app?token=secret', 'https://127.0.0.1', 'https://metadata.google.internal'])
def test_public_url_rejects_untrusted_origins(url: str) -> None:
    with pytest.raises(ApplicationError):
        public_url(url)


def test_factory_cookie_boundary() -> None:
    assert public_url('https://app.vercel.app') == 'https://app.vercel.app'
    with pytest.raises(ApplicationError):
        public_url('https://app.vercel.app', 'https://app.vercel.app')
    # vercel.app is a public suffix; distinct provider projects are separate browser sites.
    assert public_url('https://app.vercel.app', 'https://factory.vercel.app') == 'https://app.vercel.app'
