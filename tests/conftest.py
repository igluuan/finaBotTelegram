import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, MagicMock, patch

from finbot.database.models import Base


class _PatchProxy:
    def __init__(self, owner):
        self.owner = owner

    def __call__(self, target, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        mocked = patcher.start()
        self.owner._patchers.append(patcher)
        return mocked

    def dict(self, in_dict, values=(), clear=False, **kwargs):
        patcher = patch.dict(in_dict, values=values, clear=clear, **kwargs)
        patcher.start()
        self.owner._patchers.append(patcher)
        return patcher


class _SimpleMocker:
    def __init__(self):
        self._patchers = []
        self.patch = _PatchProxy(self)

    def stopall(self):
        while self._patchers:
            self._patchers.pop().stop()


@pytest.fixture
def mocker():
    helper = _SimpleMocker()
    try:
        yield helper
    finally:
        helper.stopall()

# --- Database Fixtures ---

@pytest.fixture(scope="session")
def engine():
    return create_engine("sqlite:///:memory:")

@pytest.fixture
def db_session(engine):
    Base.metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def override_get_db(db_session):
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass
    return _get_db_override

@pytest.fixture
def mock_db_context(mocker, db_session):
    mock = MagicMock()
    mock.return_value.__enter__.return_value = db_session
    mock.return_value.__exit__.return_value = None
    return mock

# --- AI Service Fixtures ---

@pytest.fixture
def mock_ai_service(mocker):
    mock = AsyncMock()
    return mock
