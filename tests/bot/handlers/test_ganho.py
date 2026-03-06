import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Message
from telegram.ext import ContextTypes, ConversationHandler
from finbot.bot.handlers.ganho import start_add_ganho, receber_tipo, receber_valor, TIPO, VALOR, DATA

@pytest.fixture
def mock_update(mocker):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.from_user = MagicMock(spec=User)
    update.message.from_user.id = 123
    update.message.text = "1 - Salário"
    update.message.reply_text = AsyncMock()
    return update

@pytest.fixture
def mock_context(mocker):
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    return context

@pytest.mark.asyncio
async def test_start_add_ganho(mock_update, mock_context):
    res = await start_add_ganho(mock_update, mock_context)
    assert res == TIPO
    mock_update.message.reply_text.assert_called_once()
    assert mock_context.user_data == {}

@pytest.mark.asyncio
async def test_receber_tipo_valid(mock_update, mock_context):
    mock_update.message.text = "1 - Salário"
    res = await receber_tipo(mock_update, mock_context)
    assert res == VALOR
    assert mock_context.user_data["categoria"] == "salario"

@pytest.mark.asyncio
async def test_receber_tipo_invalid(mock_update, mock_context):
    mock_update.message.text = "99 - Invalid"
    res = await receber_tipo(mock_update, mock_context)
    assert res == TIPO
    args, _ = mock_update.message.reply_text.call_args
    assert "Escolha uma opção válida" in args[0]

@pytest.mark.asyncio
async def test_receber_valor_valid(mock_update, mock_context):
    mock_update.message.text = "5000"
    res = await receber_valor(mock_update, mock_context)
    assert res == DATA
    assert mock_context.user_data["valor"] == 5000.0

@pytest.mark.asyncio
async def test_receber_valor_invalid(mock_update, mock_context):
    mock_update.message.text = "invalid"
    res = await receber_valor(mock_update, mock_context)
    assert res == VALOR
    args, _ = mock_update.message.reply_text.call_args
    assert "Valor inválido" in args[0]
