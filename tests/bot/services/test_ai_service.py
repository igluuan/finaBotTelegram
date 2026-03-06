import pytest
from unittest.mock import AsyncMock, MagicMock
from finbot.bot.services.ai_service import generate_content, gerar_dica_parcela, _client

@pytest.mark.asyncio
async def test_generate_content_success(mocker):
    # Mock _client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Generated content"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    
    mocker.patch("finbot.bot.services.ai_service._client", mock_client)

    res = await generate_content("prompt")
    assert res == "Generated content"

@pytest.mark.asyncio
async def test_generate_content_error(mocker):
    # Mock _client raising exception
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API Error"))
    
    mocker.patch("finbot.bot.services.ai_service._client", mock_client)

    res = await generate_content("prompt")
    assert res == ""

@pytest.mark.asyncio
async def test_gerar_dica_parcela_success(mocker):
    mock_generate = mocker.patch("finbot.bot.services.ai_service.generate_content", new_callable=AsyncMock)
    mock_generate.return_value = "Dica valida."

    dados = {
        "descricao": "Item",
        "valor_parcela": 100.0,
        "total_parcelas": 10,
        "parcelas_restantes": 9,
        "data_termino": "2024-12-01",
        "total_mensal_ativo": 500.0
    }
    res = await gerar_dica_parcela(dados)
    assert res == "Dica valida."

@pytest.mark.asyncio
async def test_gerar_dica_parcela_error(mocker):
    mock_generate = mocker.patch("finbot.bot.services.ai_service.generate_content", side_effect=Exception("Error"))

    dados = {} # Missing keys will raise KeyError in format, caught by except
    res = await gerar_dica_parcela(dados)
    assert res == "Reserve o valor da parcela alguns dias antes do vencimento para evitar imprevistos."
