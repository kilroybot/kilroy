import os
from pathlib import Path

import pytest


@pytest.fixture(scope='session')
def resources_dir() -> Path:
    return Path(os.path.dirname(__file__)) / 'resources'
