import os
import pytest
from tests.persistence.conftest import database_url, database, project_settings


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if '/tests/live/' in str(item.path):
            flag='F01_LIVE_MODEL_ACCEPTANCE' if item.path.name=='test_model_acceptance.py' else 'F01_LIVE_VERCEL_ACCEPTANCE'
            if os.environ.get(flag)!='1':
                item.add_marker(pytest.mark.skip(reason='Disposable live provider acceptance is explicit opt-in.'))
