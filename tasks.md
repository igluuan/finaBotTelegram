# 💵 Módulo `/add-ganho` — Registro de Ganhos

> Registra salário, freelance, renda extra e qualquer entrada financeira  
> Integra com os módulos de gastos e parcelas para balanço real

---

## 1. Estrutura de Arquivos

```
finbot/
├── bot/
│   ├── handlers/
│   │   └── ganho.py          ← Handler principal
│   └── database/
│       ├── models.py         ← Adicionar model Ganho
│       └── crud.py           ← Adicionar operações CRUD
```

---

## 2. Model — `database/models.py`

```python
class Ganho(Base):
    __tablename__ = "ganhos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, nullable=False, index=True)
    valor       = Column(Float, nullable=False)
    categoria   = Column(String(50), nullable=False)  # salario, freelance, investimento, outros
    descricao   = Column(String(255))
    recorrente  = Column(Boolean, default=False)      # repetir todo mês?
    dia_recebimento = Column(Integer, nullable=True)  # dia do mês (se recorrente)
    data        = Column(Date, default=date.today)
    created_at  = Column(DateTime, default=datetime.utcnow)
```

---

## 3. Categorias de Ganho

| Categoria | Exemplos |
|---|---|
| `salario` | CLT, PJ fixo mensal |
| `freelance` | Projetos avulsos, bicos |
| `investimento` | Dividendos, CDB, rendimentos |
| `aluguel` | Renda de imóvel |
| `bonus` | 13º, PLR, bônus |
| `outros` | Presentes, reembolsos, vendas |

---

## 4. Fluxo da Conversa `/add-ganho`

```
/add-ganho
     │
     ▼
"Qual o tipo? (salário/freelance/investimento/outros)"
     │
     ▼
"Qual o valor recebido?"
     │
     ▼
"Descrição? (ex: Salário março, Projeto X)"
     │
     ▼
"É recorrente todo mês?" (Sim/Não)
     │
   [SIM]──► "Qual dia do mês você recebe?"
     │
     ▼
✅ Resumo + balanço do mês
```

---

## 5. Handler — `bot/handlers/ganho.py`

```python
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, filters
)
from database.crud import criar_ganho, listar_ganhos_mes, total_ganhos_mes
from database.crud import total_gastos_mes, total_mensal_parcelas
from database import get_db
from datetime import date

TIPO, VALOR, DESCRICAO, RECORRENTE, DIA = range(5)

CATEGORIAS = {
    "1": ("salario", "💼 Salário"),
    "2": ("freelance", "💻 Freelance"),
    "3": ("investimento", "📈 Investimento"),
    "4": ("aluguel", "🏠 Aluguel"),
    "5": ("bonus", "🎯 Bônus / 13º"),
    "6": ("outros", "📦 Outros"),
}

TECLADO_CATEGORIAS = ReplyKeyboardMarkup(
    [["1 - Salário", "2 - Freelance"], ["3 - Investimento", "4 - Aluguel"],
     ["5 - Bônus / 13º", "6 - Outros"]],
    one_time_keyboard=True, resize_keyboard=True
)

TECLADO_SIM_NAO = ReplyKeyboardMarkup(
    [["✅ Sim", "❌ Não"]], one_time_keyboard=True, resize_keyboard=True
)


async def start_add_ganho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💵 *Registrar ganho!*\n\nQual o tipo de ganho?",
        parse_mode="Markdown",
        reply_markup=TECLADO_CATEGORIAS
    )
    return TIPO


async def receber_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    numero = texto.split("-")[0].strip()

    if numero not in CATEGORIAS:
        await update.message.reply_text("❌ Escolha uma opção válida.", reply_markup=TECLADO_CATEGORIAS)
        return TIPO

    context.user_data["categoria"], context.user_data["categoria_label"] = CATEGORIAS[numero]
    await update.message.reply_text(
        f"{context.user_data['categoria_label']} selecionado.\n\n💰 Qual o *valor recebido*?\nEx: `3500` ou `3500.50`",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return VALOR


async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(update.message.text.strip().replace(",", "."))
        if valor <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Ex: `3500` ou `1200.50`", parse_mode="Markdown")
        return VALOR

    context.user_data["valor"] = valor
    await update.message.reply_text(
        "📝 *Descrição* (opcional — pressione /pular para deixar em branco):\nEx: `Salário março`, `Projeto Logo`",
        parse_mode="Markdown"
    )
    return DESCRICAO


async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["descricao"] = update.message.text.strip()
    await update.message.reply_text(
        "🔄 Esse ganho se repete *todo mês*?",
        parse_mode="Markdown",
        reply_markup=TECLADO_SIM_NAO
    )
    return RECORRENTE


async def pular_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["descricao"] = context.user_data["categoria_label"]
    await update.message.reply_text(
        "🔄 Esse ganho se repete *todo mês*?",
        parse_mode="Markdown",
        reply_markup=TECLADO_SIM_NAO
    )
    return RECORRENTE


async def receber_recorrente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.message.text.strip().lower()
    eh_recorrente = "sim" in resposta or "✅" in resposta
    context.user_data["recorrente"] = eh_recorrente

    if eh_recorrente:
        await update.message.reply_text(
            "📅 Qual o *dia do mês* que você costuma receber?\nEx: `5`",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return DIA

    return await _finalizar(update, context)


async def receber_dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dia = int(update.message.text.strip())
        if dia < 1 or dia > 31:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Dia inválido. Digite entre 1 e 31.")
        return DIA

    context.user_data["dia_recebimento"] = dia
    return await _finalizar(update, context)


async def _finalizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dados = context.user_data
    user_id = update.effective_user.id

    with get_db() as db:
        criar_ganho(db, user_id, dados)
        total_ganho_mes  = total_ganhos_mes(db, user_id)
        total_gasto_mes  = total_gastos_mes(db, user_id)
        total_parcela_mes = total_mensal_parcelas(db, user_id)

    saldo = total_ganho_mes - total_gasto_mes - total_parcela_mes
    emoji_saldo = "🟢" if saldo >= 0 else "🔴"
    recorrente_txt = f"🔄 Recorrente — todo dia {dados.get('dia_recebimento', '?')}" if dados.get("recorrente") else "📌 Registro único"

    await update.message.reply_text(
        f"✅ *{dados['descricao']}* registrado!\n\n"
        f"{dados['categoria_label']}\n"
        f"💵 *R$ {dados['valor']:.2f}*\n"
        f"{recorrente_txt}\n\n"
        f"─────────────────\n"
        f"📊 *Balanço do mês:*\n"
        f"💚 Ganhos:   R$ {total_ganho_mes:.2f}\n"
        f"🔴 Gastos:   R$ {total_gasto_mes:.2f}\n"
        f"💳 Parcelas: R$ {total_parcela_mes:.2f}\n"
        f"─────────────────\n"
        f"{emoji_saldo} *Saldo: R$ {saldo:.2f}*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelado.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── /ganhos ───────────────────────────────────────────────────

async def listar_ganhos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db() as db:
        ganhos = listar_ganhos_mes(db, user_id)
        total  = total_ganhos_mes(db, user_id)
        gastos = total_gastos_mes(db, user_id)
        parcelas = total_mensal_parcelas(db, user_id)

    if not ganhos:
        await update.message.reply_text("Nenhum ganho registrado este mês.")
        return

    linhas = [f"💵 *Ganhos de {date.today().strftime('%b/%Y')}*\n"]
    for g in ganhos:
        rec = " 🔄" if g.recorrente else ""
        linhas.append(f"• {g.descricao} — *R$ {g.valor:.2f}*{rec}")

    saldo = total - gastos - parcelas
    emoji_saldo = "🟢" if saldo >= 0 else "🔴"

    linhas.append(f"\n─────────────────")
    linhas.append(f"💚 Total ganhos:  R$ {total:.2f}")
    linhas.append(f"🔴 Total gastos:  R$ {gastos:.2f}")
    linhas.append(f"💳 Parcelas:      R$ {parcelas:.2f}")
    linhas.append(f"─────────────────")
    linhas.append(f"{emoji_saldo} *Saldo: R$ {saldo:.2f}*")

    await update.message.reply_text("\n".join(linhas), parse_mode="Markdown")


# ── Registrar handlers ────────────────────────────────────────

def get_ganho_handlers():
    conv = ConversationHandler(
        entry_points=[CommandHandler("add_ganho", start_add_ganho)],
        states={
            TIPO:       [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_tipo)],
            VALOR:      [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO:  [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao),
                CommandHandler("pular", pular_descricao)
            ],
            RECORRENTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_recorrente)],
            DIA:        [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_dia)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        conversation_timeout=300
    )
    return [
        conv,
        CommandHandler("ganhos", listar_ganhos),
    ]
```

---

## 6. CRUD — `database/crud.py`

```python
from datetime import date

def criar_ganho(db, user_id: int, dados: dict):
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
```

---

## 7. Automação — Lembrete de Ganho Recorrente

```python
# services/scheduler.py — adicionar job

@scheduler.scheduled_job("cron", hour=8, minute=0)
async def lembrar_ganhos_recorrentes():
    """Avisa se ganho recorrente ainda não foi registrado no mês"""
    hoje = date.today()
    with get_db() as db:
        ganhos_recorrentes = db.query(Ganho).filter(
            Ganho.recorrente == True,
            Ganho.dia_recebimento == hoje.day
        ).all()

    for g in ganhos_recorrentes:
        # Verifica se já foi lançado esse mês
        ja_lancado = db.query(Ganho).filter(
            Ganho.user_id == g.user_id,
            Ganho.descricao == g.descricao,
            Ganho.data >= hoje.replace(day=1)
        ).count() > 1  # > 1 pois o recorrente já está salvo

        if not ja_lancado:
            await app.bot.send_message(
                chat_id=g.user_id,
                text=f"💵 Lembrete: hoje é dia {hoje.day}, "
                     f"você costuma receber *{g.descricao}* (R$ {g.valor:.2f}).\n"
                     f"Já recebeu? Use /add\\_ganho para registrar.",
                parse_mode="Markdown"
            )
```

---

## 8. Registrar no `main.py`

```python
from bot.handlers.ganho import get_ganho_handlers

for handler in get_ganho_handlers():
    app.add_handler(handler)
```

---

## 9. Exemplo de Interação

```
👤 /add_ganho

🤖 💵 Registrar ganho!
   Qual o tipo de ganho?
   [1 - Salário]  [2 - Freelance]
   [3 - Investimento] [4 - Aluguel]
   [5 - Bônus / 13º]  [6 - Outros]

👤 1 - Salário

🤖 💼 Salário selecionado.
   Qual o valor recebido?

👤 4500

🤖 Descrição (ou /pular):

👤 Salário março

🤖 Esse ganho se repete todo mês?
   [✅ Sim]  [❌ Não]

👤 ✅ Sim

🤖 Qual o dia do mês que você costuma receber?

👤 5

🤖 ✅ Salário março registrado!

   💼 Salário
   💵 R$ 4.500,00
   🔄 Recorrente — todo dia 5

   ─────────────────
   📊 Balanço do mês:
   💚 Ganhos:   R$ 4.500,00
   🔴 Gastos:   R$ 1.230,00
   💳 Parcelas: R$   730,00
   ─────────────────
   🟢 Saldo: R$ 2.540,00
```

---

## 10. Comandos do Módulo

| Comando | Função |
|---|---|
| `/add_ganho` | Registra novo ganho |
| `/ganhos` | Lista ganhos do mês + balanço |
| `/cancelar` | Cancela o fluxo atual |

---

## 11. Edge Cases

| Situação | Tratamento |
|---|---|
| Valor inválido | Re-pergunta com exemplo |
| Categoria fora do range | Re-exibe teclado |
| Descrição pulada | Usa o nome da categoria |
| Timeout 5 min | Conversa cancelada automaticamente |
| Ganho recorrente já lançado | Lembrete não dispara novamente |