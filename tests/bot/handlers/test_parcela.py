import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import date
from telegram import Update, User, Message
from telegram.ext import ContextTypes, ConversationHandler
from finbot.bot.handlers.parcela import (
    start_add_parcela, receber_cartao, receber_descricao, receber_valor,
    receber_total_parcelas, receber_parcela_atual, receber_vencimento,
    listar_parcelas, quitar, proximo_mes,
    CARTAO, DESCRICAO, VALOR, TOTAL_PARCELAS, PARCELA_ATUAL, VENCIMENTO
)
from finbot.bot.database.models import Parcela

@pytest.fixture
def mock_update(mocker):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    
    user = MagicMock(spec=User)
    user.id = 123
    user.first_name = "Test User"
    
    update.message.from_user = user
    update.effective_user = user
    update.message.text = "4521"
    update.message.reply_text = AsyncMock()
    return update

@pytest.fixture
def mock_context(mocker):
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.args = []
    return context

@pytest.mark.asyncio
async def test_start_add_parcela(mock_update, mock_context):
    res = await start_add_parcela(mock_update, mock_context)
    assert res == CARTAO
    assert mock_context.user_data == {}

@pytest.mark.asyncio
async def test_receber_cartao_valido(mock_update, mock_context):
    mock_update.message.text = "1234"
    res = await receber_cartao(mock_update, mock_context)
    assert res == DESCRICAO
    assert mock_context.user_data["cartao"] == "1234"

@pytest.mark.asyncio
async def test_receber_cartao_invalido(mock_update, mock_context):
    mock_update.message.text = "123" # 3 digits
    res = await receber_cartao(mock_update, mock_context)
    assert res == CARTAO
    args, _ = mock_update.message.reply_text.call_args
    assert "Digite exatamente 4 dígitos" in args[0]

@pytest.mark.asyncio
async def test_receber_descricao(mock_update, mock_context):
    mock_update.message.text = "TV"
    res = await receber_descricao(mock_update, mock_context)
    assert res == VALOR
    assert mock_context.user_data["descricao"] == "TV"

@pytest.mark.asyncio
async def test_receber_valor_valido(mock_update, mock_context):
    mock_update.message.text = "2400.00"
    res = await receber_valor(mock_update, mock_context)
    assert res == TOTAL_PARCELAS
    assert mock_context.user_data["valor_total"] == 2400.0

@pytest.mark.asyncio
async def test_receber_total_parcelas_valido(mock_update, mock_context):
    mock_update.message.text = "12"
    res = await receber_total_parcelas(mock_update, mock_context)
    assert res == PARCELA_ATUAL
    assert mock_context.user_data["total_parcelas"] == 12

@pytest.mark.asyncio
async def test_receber_parcela_atual_valido(mock_update, mock_context):
    mock_update.message.text = "1"
    mock_context.user_data["total_parcelas"] = 12
    res = await receber_parcela_atual(mock_update, mock_context)
    assert res == VENCIMENTO
    assert mock_context.user_data["parcela_atual"] == 1

@pytest.mark.asyncio
async def test_receber_vencimento_valido(mocker, mock_update, mock_context):
    mock_update.message.text = "10"
    mock_context.user_data = {
        "cartao": "1234",
        "descricao": "TV",
        "valor_total": 2400.0,
        "total_parcelas": 12,
        "parcela_atual": 1
    }
    
    # Mock DB interactions
    mock_create = mocker.patch("finbot.bot.handlers.parcela.criar_parcela")
    # Mock return object of criar_parcela
    mock_parcela = MagicMock()
    mock_parcela.descricao = "TV"
    mock_parcela.valor_parcela = 200.0
    mock_parcela.total_parcelas = 12
    mock_parcela.parcela_atual = 1
    mock_parcela.parcelas_restantes = 11
    mock_parcela.dia_vencimento = 10
    mock_parcela.valor_restante = 2200.0
    mock_parcela.cartao_final = "1234"
    mock_create.return_value = mock_parcela
    
    mocker.patch("finbot.bot.handlers.parcela.total_mensal_parcelas", return_value=200.0)
    mocker.patch("finbot.bot.handlers.parcela.gerar_dica_parcela", return_value="Dica teste")
    
    res = await receber_vencimento(mock_update, mock_context)
    assert res == ConversationHandler.END
    mock_create.assert_called_once()
    
    args, _ = mock_update.message.reply_text.call_args
    assert "TV" in args[0]
    assert "Dica teste" in args[0]

@pytest.mark.asyncio
async def test_listar_parcelas_vazio(mocker, mock_update, mock_context):
    mocker.patch("finbot.bot.handlers.parcela.listar_parcelas_ativas", return_value=[])
    mocker.patch("finbot.bot.handlers.parcela.total_mensal_parcelas", return_value=0.0)
    
    await listar_parcelas(mock_update, mock_context)
    
    args, _ = mock_update.message.reply_text.call_args
    assert "Nenhuma parcela ativa" in args[0]

@pytest.mark.asyncio
async def test_listar_parcelas_com_dados(mocker, mock_update, mock_context):
    p1 = MagicMock(spec=Parcela)
    p1.cartao_final = "1234"
    p1.descricao = "TV"
    p1.valor_parcela = 100.0
    p1.parcela_atual = 1
    p1.total_parcelas = 10
    p1.dia_vencimento = 15
    p1.id = 1

    mocker.patch("finbot.bot.handlers.parcela.listar_parcelas_ativas", return_value=[p1])
    mocker.patch("finbot.bot.handlers.parcela.total_mensal_parcelas", return_value=100.0)
    
    await listar_parcelas(mock_update, mock_context)
    
    args, _ = mock_update.message.reply_text.call_args
    assert "TV" in args[0]
    assert "100.00" in args[0]

@pytest.mark.asyncio
async def test_quitar_sucesso(mocker, mock_update, mock_context):
    mock_context.args = ["1"]
    mocker.patch("finbot.bot.handlers.parcela.quitar_parcela", return_value=True)
    
    await quitar(mock_update, mock_context)
    
    args, _ = mock_update.message.reply_text.call_args
    assert "marcada como quitada" in args[0]

@pytest.mark.asyncio
async def test_proximo_mes(mocker, mock_update, mock_context):
    p1 = MagicMock(spec=Parcela)
    p1.descricao = "TV"
    p1.valor_parcela = 100.0
    p1.parcelas_restantes = 5 # > 0
    p1.dia_vencimento = 10
    p1.cartao_final = "1234"

    mocker.patch("finbot.bot.handlers.parcela.listar_parcelas_ativas", return_value=[p1])
    
    await proximo_mes(mock_update, mock_context)
    
    args, _ = mock_update.message.reply_text.call_args
    assert "Parcelas do próximo mês" in args[0]
    assert "TV" in args[0]
