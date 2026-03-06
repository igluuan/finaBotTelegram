import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes, ConversationHandler
from finbot.bot.handlers.gasto import iniciar_gasto, confirmar_gasto, receber_metodo, CONFIRMAR, METODO_PAGAMENTO
import finbot.bot.handlers.gasto as gasto_module

@pytest.fixture
def mock_update(mocker):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.from_user = MagicMock(spec=User)
    update.message.from_user.id = 123
    update.message.from_user.first_name = "Test"
    update.message.text = "10 uber"
    update.message.reply_text = AsyncMock()
    update.message.reply_chat_action = AsyncMock()
    return update

@pytest.fixture
def mock_context(mocker):
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    return context

@pytest.mark.asyncio
async def test_iniciar_gasto_high_confidence(mocker, mock_update, mock_context):
    # Mocks
    mocker.patch("finbot.bot.handlers.gasto.crud.get_user", return_value=MagicMock())
    mocker.patch("finbot.bot.handlers.gasto.parser.parse_gasto", return_value={
        "valor": 10.0,
        "categoria": "transporte",
        "descricao": "Uber",
        "confianca": 0.95
    })
    mocker.patch("finbot.bot.handlers.gasto.parser.parse_user_date", return_value="2023-01-01")
    # Mock perguntar_metodo to avoid complex logic there
    mocker.patch("finbot.bot.handlers.gasto.perguntar_metodo", new_callable=AsyncMock, return_value=METODO_PAGAMENTO)

    res = await iniciar_gasto(mock_update, mock_context)
    
    assert res == METODO_PAGAMENTO
    assert mock_context.user_data["gasto"]["valor"] == 10.0
    assert mock_context.user_data["gasto"]["categoria"] == "transporte"

@pytest.mark.asyncio
async def test_iniciar_gasto_low_confidence(mocker, mock_update, mock_context):
    mocker.patch("finbot.bot.handlers.gasto.crud.get_user", return_value=MagicMock())
    mocker.patch("finbot.bot.handlers.gasto.parser.parse_gasto", return_value={
        "valor": 10.0,
        "categoria": "transporte",
        "descricao": "Uber",
        "confianca": 0.5
    })
    mocker.patch("finbot.bot.handlers.gasto.parser.parse_user_date", return_value="2023-01-01")

    res = await iniciar_gasto(mock_update, mock_context)
    
    assert res == CONFIRMAR
    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Vou registrar assim" in args[0]

@pytest.mark.asyncio
async def test_confirmar_gasto_sim(mocker, mock_update, mock_context):
    mock_update.message.text = "sim"
    mock_context.user_data["gasto"] = {"valor": 10}
    mocker.patch("finbot.bot.handlers.gasto.perguntar_metodo", new_callable=AsyncMock, return_value=METODO_PAGAMENTO)

    res = await confirmar_gasto(mock_update, mock_context)
    assert res == METODO_PAGAMENTO

@pytest.mark.asyncio
async def test_receber_metodo(mocker, mock_update, mock_context):
    mock_update.message.text = "💳 Crédito"
    mock_context.user_data["gasto"] = {
        "user_id": 123,
        "valor": 10.0,
        "categoria": "transporte",
        "descricao": "Uber",
        "data": "2023-01-01"
    }
    
    mock_add = mocker.patch("finbot.bot.handlers.gasto.crud.add_gasto")
    mocker.patch("finbot.bot.handlers.gasto.crud.get_gastos_por_categoria", return_value=[])
    mocker.patch("finbot.bot.handlers.gasto.crud.get_orcamento_status", return_value=[])
    mocker.patch("finbot.bot.handlers.gasto.crud.get_historico_categoria", return_value=[])
    
    res = await receber_metodo(mock_update, mock_context)
    
    assert res == ConversationHandler.END
    assert mock_context.user_data["gasto"]["metodo"] == "Crédito"
    mock_add.assert_called_once()
