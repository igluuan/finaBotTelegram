import pytest
from datetime import date
from finbot.bot.database.crud import (
    create_user, get_user, add_gasto, get_gastos_mes, get_total_mes,
    add_cartao, get_cartoes_usuario, delete_cartao,
    set_orcamento, get_orcamento_status,
    criar_ganho, listar_ganhos_mes, total_ganhos_mes,
    criar_parcela, listar_parcelas_ativas, quitar_parcela, total_mensal_parcelas
)

@pytest.fixture(autouse=True)
def mock_db_context_auto(mock_db_context):
    pass

def test_user_operations(db_session):
    user = create_user(12345, "TestUser")
    assert user.telegram_id == 12345
    assert user.nome == "TestUser"
    
    fetched = get_user(12345)
    assert fetched.telegram_id == 12345

def test_gasto_operations(db_session):
    create_user(111, "User1")
    gasto = add_gasto(111, 50.0, "alimentacao", "almoco", "pix", date(2023, 10, 1))
    assert gasto.valor == 50.0
    
    gastos = get_gastos_mes(111, 10, 2023)
    assert len(gastos) == 1
    assert gastos[0].descricao == "almoco"
    
    total = get_total_mes(111, 10, 2023)
    assert total == 50.0

def test_cartao_operations(db_session):
    create_user(222, "User2")
    cartao = add_cartao(222, "1234", "Nubank", "credito")
    assert cartao.final == "1234"
    
    # Add duplicate, should return existing
    cartao2 = add_cartao(222, "1234")
    assert cartao2.id == cartao.id
    
    cartoes = get_cartoes_usuario(222)
    assert len(cartoes) == 1
    
    delete_cartao(222, "1234")
    assert len(get_cartoes_usuario(222)) == 0

def test_orcamento_operations(db_session):
    create_user(333, "User3")
    add_gasto(333, 80.0, "lazer", "cinema", "credito", date(2023, 10, 5))
    
    set_orcamento(333, "lazer", 10, 2023, 100.0)
    
    status = get_orcamento_status(333, 10, 2023)
    # Status returns list of dicts for all categories with expenses
    lazer_stat = next(s for s in status if s["categoria"] == "lazer")
    assert lazer_stat["gasto"] == 80.0
    assert lazer_stat["limite"] == 100.0
    assert lazer_stat["percentual"] == 80.0

def test_ganho_operations(db_session):
    create_user(444, "User4")
    dados = {
        "valor": 5000.0,
        "categoria": "salario",
        "descricao": "Salario Mensal",
        "data": date.today()
    }
    # criar_ganho takes db as argument
    ganho = criar_ganho(db_session, 444, dados)
    assert ganho.valor == 5000.0
    
    ganhos = listar_ganhos_mes(db_session, 444)
    assert len(ganhos) == 1
    
    total = total_ganhos_mes(db_session, 444)
    assert total == 5000.0

def test_parcela_operations(db_session):
    create_user(555, "User5")
    dados = {
        "cartao": "5678",
        "descricao": "Laptop",
        "valor_total": 3000.0,
        "total_parcelas": 10,
        "parcela_atual": 1,
        "dia_vencimento": 10
    }
    # criar_parcela takes db as argument
    parcela = criar_parcela(db_session, 555, dados)
    assert parcela.valor_parcela == 300.0
    
    ativas = listar_parcelas_ativas(db_session, 555)
    assert len(ativas) == 1
    
    total = total_mensal_parcelas(db_session, 555)
    assert total == 300.0
    
    quitar_parcela(db_session, parcela.id, 555)
    ativas = listar_parcelas_ativas(db_session, 555)
    assert len(ativas) == 0
