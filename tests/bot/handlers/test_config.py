import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Message, Document
from telegram.ext import ContextTypes
from finbot.bot.handlers.config import start, ajuda, orcamento, deletar, exportar
from finbot.bot.database.models import Gasto, Ganho

@pytest.fixture
def mock_update(mocker):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.from_user = MagicMock(spec=User)
    update.message.from_user.id = 123
    update.message.from_user.first_name = "User"
    update.effective_user = update.message.from_user
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()
    return update

@pytest.fixture
def mock_context(mocker):
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context

@pytest.mark.asyncio
async def test_start(mocker, mock_update, mock_context):
    mocker.patch("finbot.bot.handlers.config.crud.get_user", return_value=None)
    mock_create = mocker.patch("finbot.bot.handlers.config.crud.create_user")
    
    await start(mock_update, mock_context)
    
    mock_create.assert_called_once()
    mock_update.message.reply_text.assert_called_once()
    args, _ = mock_update.message.reply_text.call_args
    assert "Olá User" in args[0]

@pytest.mark.asyncio
async def test_ajuda(mock_update, mock_context):
    await ajuda(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    args, _ = mock_update.message.reply_text.call_args
    assert "Comandos do FinBot" in args[0]

@pytest.mark.asyncio
async def test_orcamento_valido(mocker, mock_update, mock_context):
    mock_context.args = ["lazer", "200"]
    mock_set = mocker.patch("finbot.bot.handlers.config.crud.set_orcamento")
    
    await orcamento(mock_update, mock_context)
    
    mock_set.assert_called_once()
    args, _ = mock_update.message.reply_text.call_args
    assert "Orçamento de *lazer* definido" in args[0]

@pytest.mark.asyncio
async def test_orcamento_invalido(mock_update, mock_context):
    mock_context.args = ["lazer"] # Missing value
    await orcamento(mock_update, mock_context)
    args, _ = mock_update.message.reply_text.call_args
    assert "Use: /orcamento" in args[0]

@pytest.mark.asyncio
async def test_deletar_sucesso(mocker, mock_update, mock_context):
    gasto = MagicMock(spec=Gasto)
    gasto.valor = 50.0
    gasto.categoria = "lazer"
    mocker.patch("finbot.bot.handlers.config.crud.delete_last_gasto", return_value=gasto)
    
    await deletar(mock_update, mock_context)
    
    args, _ = mock_update.message.reply_text.call_args
    assert "removido" in args[0]

@pytest.mark.asyncio
async def test_exportar(mocker, mock_update, mock_context):
    g1 = MagicMock(spec=Gasto)
    g1.data.isoformat.return_value = "2023-01-01"
    g1.valor = 10.0
    g1.categoria = "teste"
    g1.descricao = "desc"

    gan1 = MagicMock(spec=Ganho)
    gan1.data.isoformat.return_value = "2023-01-01"
    gan1.valor = 100.0
    gan1.categoria = "salario"
    gan1.descricao = "salario"

    mocker.patch("finbot.bot.handlers.config.crud.get_gastos_mes", return_value=[g1])
    # Patching directly where it is defined, which affects imports
    mocker.patch("finbot.bot.database.crud.listar_ganhos_mes", return_value=[gan1])
    
    # Mock context manager for get_db
    mock_db = MagicMock()
    mock_get_db = mocker.patch("finbot.bot.database.crud.get_db")
    mock_get_db.return_value.__enter__.return_value = mock_db
    
    await exportar(mock_update, mock_context)
    
    mock_update.message.reply_document.assert_called_once()
