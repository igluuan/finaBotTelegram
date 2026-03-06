import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from finbot.bot.database.models import Base
from finbot.bot.database.crud import get_db
import finbot.bot.database.crud as crud_module
from unittest.mock import AsyncMock, MagicMock

# --- Database Fixtures ---

@pytest.fixture(autouse=True)
def mock_config(mocker):
    mocker.patch("finbot.config.ALLOWED_USER_ID", None)
    # Também patch em bot.config se existir
    mocker.patch.dict("os.environ", {"ALLOWED_USER_ID": ""})

@pytest.fixture(scope="session")
def engine():
    from sqlalchemy.pool import StaticPool
    return create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False}, 
        poolclass=StaticPool
    )

@pytest.fixture(autouse=True)
def db_session(engine):
    Base.metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    
    # Patch global do get_db para usar essa sessão
    original_get_db = crud_module.get_db
    
    # Patch do SessionLocal no crud module para usar nosso engine/session
    crud_module.engine = engine
    crud_module.SessionLocal = sessionmaker(bind=engine)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    Base.metadata.drop_all(engine)
    
    # Restore
    # crud_module.get_db = original_get_db # Não é fácil restaurar generator, mas ok para testes

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
    mock = mocker.patch("finbot.bot.database.crud.get_db")
    mock.return_value.__enter__.return_value = db_session
    mock.return_value.__exit__.return_value = None
    return mock

# --- AI Service Fixtures ---

@pytest.fixture
def mock_ai_service(mocker):
    # Mock the generate_content function in the ai_service module
    mock = mocker.patch("finbot.bot.services.ai_service.generate_content", new_callable=AsyncMock)
    return mock
