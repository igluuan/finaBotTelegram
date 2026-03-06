from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Cartao(Base):
    __tablename__ = "cartoes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('usuarios.telegram_id'), nullable=False)
    final = Column(String(4), nullable=False)  # Ex: 1234
    nome = Column(String(50)) # Ex: Nubank, Inter (Opcional)
    tipo = Column(String(20)) # credito, debito, ambos
    created_at = Column(DateTime, default=func.now())

    usuario = relationship("Usuario", back_populates="cartoes")

class Usuario(Base):
    __tablename__ = 'usuarios'
    telegram_id = Column(Integer, primary_key=True)
    nome = Column(String)
    moeda = Column(String, default='BRL')
    dia_fechamento = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())

    gastos = relationship("Gasto", back_populates="usuario")
    categorias = relationship("Categoria", back_populates="usuario")
    orcamentos = relationship("Orcamento", back_populates="usuario")
    cartoes = relationship("Cartao", back_populates="usuario")

class Parcela(Base):
    __tablename__ = "parcelas"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(Integer, nullable=False, index=True)
    cartao_final     = Column(String(4), nullable=False)
    descricao        = Column(String(255), nullable=False)
    valor_total      = Column(Float, nullable=False)
    valor_parcela    = Column(Float, nullable=False)   # calculado: valor_total / total_parcelas
    total_parcelas   = Column(Integer, nullable=False)
    parcela_atual    = Column(Integer, nullable=False)
    dia_vencimento   = Column(Integer, nullable=False)
    data_inicio      = Column(Date, nullable=False)
    quitada          = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=func.now())

    @property
    def parcelas_restantes(self):
        return self.total_parcelas - self.parcela_atual

    @property
    def valor_restante(self):
        return self.valor_parcela * (self.total_parcelas - self.parcela_atual + 1)

class Categoria(Base):
    __tablename__ = 'categorias'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('usuarios.telegram_id'))
    nome = Column(String)
    emoji = Column(String)
    orcamento_mensal = Column(Float, default=0)

    usuario = relationship("Usuario", back_populates="categorias")

class Gasto(Base):
    __tablename__ = 'gastos'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('usuarios.telegram_id'))
    valor = Column(Float, nullable=False)
    categoria = Column(String, nullable=False)
    descricao = Column(String)
    metodo_pagamento = Column(String)  # Novo campo: pix, dinheiro, debito, credito(1234)
    data = Column(Date, default=func.current_date())
    created_at = Column(DateTime, default=func.now())

    usuario = relationship("Usuario", back_populates="gastos")

class Orcamento(Base):
    __tablename__ = 'orcamentos'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('usuarios.telegram_id'))
    categoria = Column(String)
    mes = Column(Integer)
    ano = Column(Integer)
    limite = Column(Float)

    usuario = relationship("Usuario", back_populates="orcamentos")

class Ganho(Base):
    __tablename__ = "ganhos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, nullable=False, index=True)
    valor       = Column(Float, nullable=False)
    categoria   = Column(String(50), nullable=False)  # salario, freelance, investimento, outros
    descricao   = Column(String(255))
    recorrente  = Column(Boolean, default=False)      # repetir todo mês?
    dia_recebimento = Column(Integer, nullable=True)  # dia do mês (se recorrente)
    data        = Column(Date, default=func.current_date())
    created_at  = Column(DateTime, default=func.now())
