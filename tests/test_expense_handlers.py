import sys
from unittest.mock import MagicMock

# Mocks globais para dependências externas não instaladas no ambiente de teste
# Isso permite rodar os testes unitários sem precisar instalar todo o requirements.txt
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()
sys.modules['sqlalchemy.sql'] = MagicMock()
sys.modules['sqlalchemy.ext'] = MagicMock()
sys.modules['sqlalchemy.ext.declarative'] = MagicMock()

# Mock ensure_user decorator to bypass DB check
mock_decorators = MagicMock()
def mock_ensure_user(func):
    return func
mock_decorators.ensure_user = mock_ensure_user
sys.modules['finbot.interfaces.telegram.decorators'] = mock_decorators

# Mock ZoneInfo to avoid tzdata dependency issues on Windows without tzdata installed
import zoneinfo
zoneinfo.ZoneInfo = MagicMock()

import pytest
from unittest.mock import AsyncMock, patch
from finbot.interfaces.telegram.handlers.expense import _process_amount, start_expense
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes, ConversationHandler

@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 12345
    return update

@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    return context

@pytest.mark.asyncio
class TestProcessAmount:
    
    async def test_valid_integer(self, mock_update):
        """Testa conversão de string inteira válida."""
        result = await _process_amount(mock_update, "100")
        assert result == 100.0
        mock_update.message.reply_text.assert_not_called()

    async def test_valid_float_dot(self, mock_update):
        """Testa conversão de float com ponto."""
        result = await _process_amount(mock_update, "10.50")
        assert result == 10.5
        mock_update.message.reply_text.assert_not_called()

    async def test_valid_float_comma(self, mock_update):
        """Testa conversão de float com vírgula (formato PT-BR)."""
        result = await _process_amount(mock_update, "10,50")
        assert result == 10.5
        mock_update.message.reply_text.assert_not_called()

    async def test_invalid_format_text(self, mock_update):
        """Testa entrada com texto não numérico."""
        result = await _process_amount(mock_update, "abc")
        assert result is None
        mock_update.message.reply_text.assert_called_with("Valor de gasto inválido.")

    async def test_zero_value(self, mock_update):
        """Testa valor zero (inválido)."""
        result = await _process_amount(mock_update, "0")
        assert result is None
        mock_update.message.reply_text.assert_called_with("❌ O valor deve ser maior que zero.")

    async def test_negative_value(self, mock_update):
        """Testa valor negativo (inválido)."""
        result = await _process_amount(mock_update, "-10")
        assert result is None
        mock_update.message.reply_text.assert_called_with("❌ O valor deve ser maior que zero.")

    async def test_value_too_high(self, mock_update):
        """Testa valor acima do limite permitido."""
        result = await _process_amount(mock_update, "1000001")
        assert result is None
        mock_update.message.reply_text.assert_called_with("⚠️ Valor muito alto. Verifique se digitou corretamente.")

    async def test_boundary_value_high(self, mock_update):
        """Testa valor no limite máximo permitido."""
        result = await _process_amount(mock_update, "1000000")
        assert result == 1000000.0
        mock_update.message.reply_text.assert_not_called()

    async def test_unexpected_empty_string(self, mock_update):
        """Testa string vazia."""
        result = await _process_amount(mock_update, "")
        assert result is None
        # ValueError ao tentar float("")
        mock_update.message.reply_text.assert_called_with("Valor de gasto inválido.")

@pytest.mark.asyncio
class TestStartExpense:
    
    @patch('finbot.interfaces.telegram.handlers.expense.parser_service.parse_expense')
    @patch('finbot.interfaces.telegram.handlers.expense.parser_service.parse_user_date')
    @patch('finbot.interfaces.telegram.handlers.expense._confirm_ai')
    async def test_start_expense_success(self, mock_confirm_ai, mock_parse_date, mock_parse_expense, mock_update, mock_context):
        """Testa fluxo de sucesso do start_expense."""
        # Setup mocks
        mock_update.message.text = "almoço 25"
        mock_parse_expense.return_value = {
            "amount": 25.0,
            "category": "alimentacao",
            "description": "almoço",
            "confidence": 0.9
        }
        mock_parse_date.return_value = "2023-10-27"
        mock_confirm_ai.return_value = None  # Confiança alta, pula confirmação
        
        # Executa
        # Precisamos mockar ask_payment_method pois é chamado no final
        with patch('finbot.interfaces.telegram.handlers.expense.ask_payment_method', new_callable=AsyncMock) as mock_ask_payment:
            mock_ask_payment.return_value = 2  # PAYMENT_METHOD state
            
            result = await start_expense(mock_update, mock_context)
            
            # Verificações
            assert result == 2
            assert mock_context.user_data["expense"]["amount"] == 25.0
            assert mock_context.user_data["expense"]["category"] == "alimentacao"

    async def test_start_expense_no_text(self, mock_update, mock_context):
        """Testa start_expense sem texto na mensagem."""
        mock_update.message.text = None
        result = await start_expense(mock_update, mock_context)
        assert result == ConversationHandler.END

    @patch('finbot.interfaces.telegram.handlers.expense.parser_service.parse_expense')
    async def test_start_expense_parse_error(self, mock_parse_expense, mock_update, mock_context):
        """Testa erro no parsing da despesa."""
        mock_update.message.text = "invalid text"
        mock_parse_expense.return_value = {"error": "No match"}
        
        result = await start_expense(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        mock_update.message.reply_text.assert_called_with(
            "❓ Não entendi esse gasto. Tente algo como '35 uber' ou 'almoço 20'."
        )
