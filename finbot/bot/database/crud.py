from sqlalchemy import create_engine, func, extract
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict

# Assuming run from finbot directory and config.py is in path
try:
    from ...config import DATABASE_URL
except ImportError:
    from config import DATABASE_URL

from .models import Base, Usuario, Gasto, Orcamento, Categoria, Parcela, Ganho

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Ganhos ---
def criar_ganho(db, user_id: int, dados: dict) -> Ganho:
    ganho = Ganho(
        user_id         = user_id,
        valor           = dados["valor"],
        categoria       = dados["categoria"],
        descricao       = dados["descricao"],
        recorrente      = dados.get("recorrente", False),
        dia_recebimento = dados.get("dia_recebimento"),
        data            = date.today(),
    )
    db.add(ganho)
    db.commit()
    db.refresh(ganho)
    return ganho

def listar_ganhos_mes(db, user_id: int):
    hoje = date.today()
    return db.query(Ganho).filter(
        Ganho.user_id == user_id,
        Ganho.data >= hoje.replace(day=1)
    ).order_by(Ganho.data.desc()).all()

def total_ganhos_mes(db, user_id: int) -> float:
    ganhos = listar_ganhos_mes(db, user_id)
    return sum(g.valor for g in ganhos)

def total_gastos_mes(db, user_id: int) -> float:
    hoje = date.today()
    gastos = db.query(Gasto).filter(
        Gasto.user_id == user_id,
        Gasto.data >= hoje.replace(day=1)
    ).all()
    return sum(g.valor for g in gastos)

# --- Parcelas ---
def criar_parcela(db, user_id: int, dados: dict) -> Parcela:
    parcela = Parcela(
        user_id        = user_id,
        cartao_final   = dados["cartao"],
        descricao      = dados["descricao"],
        valor_total    = dados["valor_total"],
        valor_parcela  = round(dados["valor_total"] / dados["total_parcelas"], 2),
        total_parcelas = dados["total_parcelas"],
        parcela_atual  = dados["parcela_atual"],
        dia_vencimento = dados["dia_vencimento"],
        data_inicio    = date.today(),
    )
    db.add(parcela)
    db.commit()
    db.refresh(parcela)
    return parcela

def listar_parcelas_ativas(db, user_id: int, cartao: str = None):
    query = db.query(Parcela).filter(
        Parcela.user_id == user_id,
        Parcela.quitada == False
    )
    if cartao:
        query = query.filter(Parcela.cartao_final == cartao)
    return query.order_by(Parcela.cartao_final, Parcela.dia_vencimento).all()

def quitar_parcela(db, parcela_id: int, user_id: int) -> bool:
    parcela = db.query(Parcela).filter(
        Parcela.id == parcela_id,
        Parcela.user_id == user_id
    ).first()
    if not parcela:
        return False
    parcela.quitada = True
    db.commit()
    return True

def total_mensal_parcelas(db, user_id: int) -> float:
    parcelas = listar_parcelas_ativas(db, user_id)
    return sum(p.valor_parcela for p in parcelas)

# --- Usuario ---
def get_user(telegram_id: int) -> Optional[Usuario]:
    with get_db() as db:
        return db.query(Usuario).filter(Usuario.telegram_id == telegram_id).first()

def create_user(telegram_id: int, nome: str) -> Usuario:
    with get_db() as db:
        user = Usuario(telegram_id=telegram_id, nome=nome)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

# --- Gastos ---
def add_gasto(user_id: int, valor: float, categoria: str, descricao: str) -> Gasto:
    with get_db() as db:
        gasto = Gasto(user_id=user_id, valor=valor, categoria=categoria, descricao=descricao, data=date.today())
        db.add(gasto)
        db.commit()
        db.refresh(gasto)
        return gasto

def get_gastos_periodo(user_id: int, start_date: date, end_date: date) -> List[Gasto]:
    with get_db() as db:
        return db.query(Gasto).filter(
            Gasto.user_id == user_id,
            Gasto.data >= start_date,
            Gasto.data <= end_date
        ).all()

def get_gastos_mes(user_id: int, mes: int, ano: int) -> List[Gasto]:
    with get_db() as db:
        return db.query(Gasto).filter(
            Gasto.user_id == user_id,
            extract('month', Gasto.data) == mes,
            extract('year', Gasto.data) == ano
        ).all()

def get_total_mes(user_id: int, mes: int, ano: int) -> float:
    with get_db() as db:
        result = db.query(func.sum(Gasto.valor)).filter(
            Gasto.user_id == user_id,
            extract('month', Gasto.data) == mes,
            extract('year', Gasto.data) == ano
        ).scalar()
        return result if result else 0.0

def get_gastos_por_categoria(user_id: int, mes: int, ano: int) -> List[Dict]:
    with get_db() as db:
        results = db.query(
            Gasto.categoria,
            func.sum(Gasto.valor).label('total')
        ).filter(
            Gasto.user_id == user_id,
            extract('month', Gasto.data) == mes,
            extract('year', Gasto.data) == ano
        ).group_by(Gasto.categoria).all()
        
        return [{"categoria": r[0], "total": r[1]} for r in results]

def delete_last_gasto(user_id: int) -> Optional[Gasto]:
    with get_db() as db:
        last_gasto = db.query(Gasto).filter(Gasto.user_id == user_id).order_by(Gasto.id.desc()).first()
        if last_gasto:
            db.delete(last_gasto)
            db.commit()
            return last_gasto
        return None

# --- Orcamentos ---
def set_orcamento(user_id: int, categoria: str, mes: int, ano: int, limite: float):
    with get_db() as db:
        orcamento = db.query(Orcamento).filter(
            Orcamento.user_id == user_id,
            Orcamento.categoria == categoria,
            Orcamento.mes == mes,
            Orcamento.ano == ano
        ).first()
        
        if orcamento:
            orcamento.limite = limite
        else:
            orcamento = Orcamento(user_id=user_id, categoria=categoria, mes=mes, ano=ano, limite=limite)
            db.add(orcamento)
        db.commit()

def get_orcamento_status(user_id: int, mes: int, ano: int) -> List[Dict]:
    # Retorna lista com categoria, gasto atual, limite e percentual
    stats = []
    gastos_cat = get_gastos_por_categoria(user_id, mes, ano)
    
    with get_db() as db:
        for cat_data in gastos_cat:
            cat_name = cat_data['categoria']
            total_gasto = cat_data['total']
            
            orcamento = db.query(Orcamento).filter(
                Orcamento.user_id == user_id,
                Orcamento.categoria == cat_name,
                Orcamento.mes == mes,
                Orcamento.ano == ano
            ).first()
            
            limite = orcamento.limite if orcamento else 0
            percentual = (total_gasto / limite * 100) if limite > 0 else 0
            
            stats.append({
                "categoria": cat_name,
                "gasto": total_gasto,
                "limite": limite,
                "percentual": percentual
            })
    return stats

# --- Categorias Historico ---
def get_historico_categoria(user_id: int, categoria: str, dias: int = 30) -> List[Gasto]:
    # Retorna gastos recentes de uma categoria para análise de anomalias
    # Simplificação: pegando últimos X gastos da categoria, independente da data exata se for muito antigo
    # Mas o prompt pede "últimos 30 dias". Vamos implementar filtro de data.
    from datetime import timedelta
    limit_date = date.today() - timedelta(days=dias)
    
    with get_db() as db:
        return db.query(Gasto).filter(
            Gasto.user_id == user_id,
            Gasto.categoria == categoria,
            Gasto.data >= limit_date
        ).all()
