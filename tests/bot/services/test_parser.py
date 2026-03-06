import pytest
from datetime import date, timedelta
from finbot.bot.services.parser import parse_user_date, _local_parse_gasto, parse_gasto, analise_mensal, check_anomalia
import json
from unittest.mock import AsyncMock

class TestParserDate:
    def test_ontem(self):
        hoje = date(2023, 10, 15)
        assert parse_user_date("ontem", hoje) == date(2023, 10, 14)

    def test_dd_mm(self):
        hoje = date(2023, 10, 15)
        assert parse_user_date("10/05", hoje) == date(2023, 5, 10)
        # Should fallback to previous year if date is in the future
        assert parse_user_date("20/12", hoje) == date(2022, 12, 20)
    
    def test_dd_mm_yyyy(self):
        hoje = date(2023, 10, 15)
        assert parse_user_date("01/01/2022", hoje) == date(2022, 1, 1)

    def test_dd_mm_yy(self):
        hoje = date(2023, 10, 15)
        assert parse_user_date("01/01/22", hoje) == date(2022, 1, 1)

    def test_invalid_date(self):
        hoje = date(2023, 10, 15)
        assert parse_user_date("invalid", hoje) == hoje

class TestLocalParser:
    def test_simple_gasto(self):
        res = _local_parse_gasto("10 uber")
        assert res["valor"] == 10.0
        assert res["categoria"] == "transporte"
        assert res["descricao"] == "Uber"

    def test_comma_separator(self):
        res = _local_parse_gasto("7,50 almoco")
        assert res["valor"] == 7.5
        assert res["categoria"] == "alimentacao"

    def test_unknown_category(self):
        res = _local_parse_gasto("500.00 desconhecido")
        assert res["valor"] == 500.0
        assert res["categoria"] == "outros"

    def test_invalid_input(self):
        res = _local_parse_gasto("apenas texto")
        assert res["erro"] == "nao_reconhecido"

@pytest.mark.asyncio
class TestAIParser:
    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        self.mock_generate = mocker.patch("finbot.bot.services.parser.generate_content", new_callable=AsyncMock)

    async def test_parse_gasto_success(self):
        mock_response = json.dumps({
            "valor": 35.00,
            "categoria": "transporte",
            "descricao": "Uber",
            "confianca": 0.95
        })
        self.mock_generate.return_value = f"```json\n{mock_response}\n```"

        res = await parse_gasto("uber 35")
        assert res["valor"] == 35.0
        assert res["categoria"] == "transporte"

    async def test_parse_gasto_fallback(self):
        self.mock_generate.return_value = "invalid json"
        # Should fallback to local parser
        res = await parse_gasto("10 almoco")
        assert res["valor"] == 10.0
        assert res["categoria"] == "alimentacao"

    async def test_analise_mensal(self):
        expected_response = "Analise mensal..."
        self.mock_generate.return_value = expected_response
        res = await analise_mensal("dados...")
        assert res == expected_response

    async def test_check_anomalia(self):
        mock_response = json.dumps({
            "incomum": True,
            "motivo": "Alto valor",
            "percentual_acima": 50
        })
        self.mock_generate.return_value = mock_response
        res = await check_anomalia("hist", "novo")
        assert res["incomum"] is True
