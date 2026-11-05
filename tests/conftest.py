import pytest
from tests.helpers import FIXTURES


@pytest.fixture
def official_lookup():
    return (FIXTURES / "codes.csv").read_bytes()
