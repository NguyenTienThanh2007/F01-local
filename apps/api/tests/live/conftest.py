import os
import pytest
from tests.persistence.conftest import database_url, database, project_settings


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get('F01_LIVE_VERCEL_ACCEPTANCE') != '1':
        for item in items:
            if '/tests/live/' in str(item.path):
                item.add_marker(pytest.mark.skip(reason='Disposable live provider acceptance is explicit opt-in.'))
