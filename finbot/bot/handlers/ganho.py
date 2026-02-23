from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, filters
)
from bot.database.crud import criar_ganho, listar_ganhos_mes, total_ganhos_mes
from bot.database.crud import total_gastos_mes, total_mensal_parcelas, get_db
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
