import sys
from unittest.mock import MagicMock

# Mock sqlalchemy and google.genai modules globally before any imports
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()
sys.modules['sqlalchemy.sql'] = MagicMock()
sys.modules['sqlalchemy.ext'] = MagicMock()
sys.modules['sqlalchemy.ext.declarative'] = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()

# Mock ZoneInfo
import zoneinfo
zoneinfo.ZoneInfo = MagicMock()

# Mock ensure_user decorator to bypass DB check
mock_decorators = MagicMock()
def mock_ensure_user(func):
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper
mock_decorators.ensure_user = mock_ensure_user
sys.modules['finbot.interfaces.telegram.decorators'] = mock_decorators

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import date

# Now we can import the modules to test
from finbot.interfaces.telegram.handlers import expense
from telegram.ext import ConversationHandler

# -----------------------------------------------------------------------------
# Test Data & Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_update():
    update = MagicMock()
    update.effective_user.id = 12345
    update.message.text = "test"
    update.message.reply_text = AsyncMock()
    update.message.reply_chat_action = AsyncMock()
    return update

@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {}
    return context

@pytest.fixture
def mock_db_session():
    session = MagicMock()
    # Mock query return values as needed
    return session

@pytest.fixture
def mock_get_db(mock_db_session):
    """Mocks get_db context manager."""
    class MockDBContext:
        def __enter__(self):
            return mock_db_session
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    return MockDBContext()

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_history_item():
    class Item:
        def __init__(self, amount, date_val, description):
            self.amount = amount
            self.date = date_val
            self.description = description
    return Item

@pytest.mark.asyncio
async def test_full_expense_flow_success(mock_update, mock_context, mock_get_db, mock_db_session):
    """
    Test complete flow: Start -> Parse -> Confirm (Auto) -> Payment Method -> Save
    """
    
    # 1. Setup Mocks
    with patch('finbot.interfaces.telegram.handlers.expense.get_db', return_value=mock_get_db), \
         patch('finbot.services.finance_service.get_db', return_value=mock_get_db), \
         patch('finbot.services.parser_service.generate_content', new_callable=AsyncMock) as mock_ai_parser, \
         patch('finbot.services.finance_service.generate_content', new_callable=AsyncMock) as mock_ai_finance, \
         patch('finbot.interfaces.telegram.handlers.expense.ExpenseRepository') as MockExpenseRepo, \
         patch('finbot.services.finance_service.ExpenseRepository') as MockServiceExpenseRepo, \
         patch('finbot.services.finance_service.BudgetRepository') as MockBudgetRepo, \
         patch('finbot.interfaces.telegram.handlers.expense.CardRepository') as MockCardRepo:
        
        # Configure AI responses
        mock_ai_parser.return_value = '```json\n{"valor": 50.00, "categoria": "alimentacao", "descricao": "Almoço", "confianca": 0.95}\n```'
        mock_ai_finance.return_value = '```json\n{"incomum": false}\n```'

        # Configure Repositories
        # Budget check returns no alert
        MockBudgetRepo.get_status.return_value = [{'category': 'alimentacao', 'limit': 1000, 'percentage': 10}]
        # Expense history for budget check
        MockServiceExpenseRepo.get_by_category_monthly.return_value = [{'category': 'alimentacao', 'total': 100.0}]
        # No previous anomaly history
        MockServiceExpenseRepo.get_category_history.return_value = []
        
        # 2. Start Expense
        mock_update.message.text = "almoço 50"
        state = await expense.start_expense(mock_update, mock_context)
        
        assert state == expense.PAYMENT_METHOD
        assert mock_context.user_data["expense"]["amount"] == 50.0
        assert mock_context.user_data["expense"]["category"] == "alimentacao"
        
        # 3. Select Payment Method (No cards registered)
        MockCardRepo.get_all.return_value = []
        MockCardRepo.get_unique_used_cards.return_value = []
        
        mock_update.message.text = "Débito"
        state = await expense.receive_payment_method(mock_update, mock_context)
        
        assert state == ConversationHandler.END
        
        # 4. Verify DB Interaction
        # Check if ExpenseRepository.create was called
        # Note: it's called in a separate thread, so we might need to verify differently or trust the flow reached that point.
        # Since we are mocking everything, including get_db, the thread will use the mock.
        # However, verifying calls across threads with mocks can be tricky if the thread is not joined.
        # But asyncio.to_thread waits for the thread to finish.
        
        MockExpenseRepo.create.assert_called_once()
        call_args = MockExpenseRepo.create.call_args
        assert call_args[0][1] == 12345  # user_id
        assert call_args[0][2] == 50.0   # amount
        assert call_args[0][3] == "alimentacao" # category
        assert call_args[1]['payment_method'] == "Débito"

@pytest.mark.asyncio
async def test_expense_flow_low_confidence(mock_update, mock_context, mock_get_db):
    """Test flow when AI confidence is low."""
    
    with patch('finbot.interfaces.telegram.handlers.expense.get_db', return_value=mock_get_db), \
         patch('finbot.services.parser_service.generate_content', new_callable=AsyncMock) as mock_ai_parser:
        
        mock_ai_parser.return_value = '```json\n{"valor": 100, "categoria": "lazer", "descricao": "Cinema", "confianca": 0.5}\n```'
        
        mock_update.message.text = "cinema 100"
        state = await expense.start_expense(mock_update, mock_context)
        
        assert state == expense.CONFIRM
        # Verify confirmation message
        mock_update.message.reply_text.assert_called()
        args = mock_update.message.reply_text.call_args[0]
        assert "Confirma" in args[0] or "R$ 100.0" in args[0]

@pytest.mark.asyncio
async def test_expense_budget_alert(mock_update, mock_context, mock_get_db):
    """Test budget alert triggering."""
    
    with patch('finbot.interfaces.telegram.handlers.expense.get_db', return_value=mock_get_db), \
         patch('finbot.services.finance_service.get_db', return_value=mock_get_db), \
         patch('finbot.services.parser_service.generate_content', new_callable=AsyncMock) as mock_ai_parser, \
         patch('finbot.services.finance_service.generate_content', new_callable=AsyncMock) as mock_ai_finance, \
         patch('finbot.interfaces.telegram.handlers.expense.ExpenseRepository') as MockExpenseRepo, \
         patch('finbot.services.finance_service.ExpenseRepository') as MockServiceExpenseRepo, \
         patch('finbot.services.finance_service.BudgetRepository') as MockBudgetRepo, \
         patch('finbot.interfaces.telegram.handlers.expense.CardRepository') as MockCardRepo:

        # Setup AI
        mock_ai_parser.return_value = '```json\n{"valor": 90.00, "categoria": "lazer", "descricao": "Jogo", "confianca": 0.95}\n```'
        mock_ai_finance.return_value = '```json\n{"incomum": false}\n```'

        # Setup Budget Alert (Trigger when > 80%)
        # Limit 100, spent 90 -> 90%
        MockBudgetRepo.get_status.return_value = [{'category': 'lazer', 'limit': 100.0, 'percentage': 90.0}]
        MockServiceExpenseRepo.get_by_category_monthly.return_value = [{'category': 'lazer', 'total': 90.0}]
        MockServiceExpenseRepo.get_category_history.return_value = []
        MockCardRepo.get_all.return_value = []
        MockCardRepo.get_unique_used_cards.return_value = []

        # Flow
        mock_update.message.text = "jogo 90"
        await expense.start_expense(mock_update, mock_context)
        
        mock_update.message.text = "Pix"
        await expense.receive_payment_method(mock_update, mock_context)
        
        # Verify Alert in response
        # Last reply should contain the success message + alert
        args = mock_update.message.reply_text.call_args[0]
        response_text = args[0]
        assert "Atenção" in response_text
        assert "80%" in response_text

@pytest.mark.asyncio
async def test_anomaly_detection_alert(mock_update, mock_context, mock_get_db, mock_history_item):
    """Test anomaly detection warning."""
    
    with patch('finbot.interfaces.telegram.handlers.expense.get_db', return_value=mock_get_db), \
         patch('finbot.services.finance_service.get_db', return_value=mock_get_db), \
         patch('finbot.services.parser_service.generate_content', new_callable=AsyncMock) as mock_ai_parser, \
         patch('finbot.services.finance_service.generate_content', new_callable=AsyncMock) as mock_ai_finance, \
         patch('finbot.interfaces.telegram.handlers.expense.ExpenseRepository') as MockExpenseRepo, \
         patch('finbot.services.finance_service.ExpenseRepository') as MockServiceExpenseRepo, \
         patch('finbot.services.finance_service.BudgetRepository') as MockBudgetRepo, \
         patch('finbot.interfaces.telegram.handlers.expense.CardRepository') as MockCardRepo:

        # Setup AI
        mock_ai_parser.return_value = '```json\n{"valor": 5000.00, "categoria": "alimentacao", "descricao": "Jantar", "confianca": 0.99}\n```'
        mock_ai_finance.return_value = '```json\n{"incomum": true, "motivo": "Valor muito alto", "percentual_acima": 500}\n```'

        # Setup Normal Budget
        MockBudgetRepo.get_status.return_value = []
        MockServiceExpenseRepo.get_by_category_monthly.return_value = []
        # Return some history for anomaly check to run
        item = mock_history_item(amount=50.0, date_val=date.today(), description="Normal")
        MockServiceExpenseRepo.get_category_history.return_value = [item]
        
        MockCardRepo.get_all.return_value = []
        MockCardRepo.get_unique_used_cards.return_value = []

        # Flow
        mock_update.message.text = "jantar 5000"
        await expense.start_expense(mock_update, mock_context)
        
        mock_update.message.text = "Dinheiro"
        await expense.receive_payment_method(mock_update, mock_context)
        
        # Verify Anomaly Warning
        # It sends success message THEN anomaly warning
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2
        anomaly_msg = calls[-1][0][0]
        assert "Gasto incomum detectado" in anomaly_msg
        assert "Valor muito alto" in anomaly_msg
