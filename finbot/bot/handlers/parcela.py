from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, filters
)
from ..database.crud import criar_parcela, listar_parcelas_ativas, quitar_parcela, total_mensal_parcelas, get_db
from ..services.ai_service import gerar_dica_parcela
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

# Estados da conversa
CARTAO, DESCRICAO, VALOR, TOTAL_PARCELAS, PARCELA_ATUAL, VENCIMENTO = range(6)


# ── /add-parcela ──────────────────────────────────────────────

async def start_add_parcela(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💳 Vamos registrar uma parcela!\n\n"
        "Qual o *final do cartão*? (4 dígitos)\n"
        "Ex: `4521`",
        parse_mode="Markdown"
    )
    return CARTAO


async def receber_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cartao = update.message.text.strip()
    if not cartao.isdigit() or len(cartao) != 4:
        await update.message.reply_text("❌ Digite exatamente 4 dígitos. Ex: `4521`", parse_mode="Markdown")
        return CARTAO
    context.user_data["cartao"] = cartao
    await update.message.reply_text("🛍️ Qual é a *descrição* da compra?\nEx: `TV Samsung 55'`", parse_mode="Markdown")
    return DESCRICAO


async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["descricao"] = update.message.text.strip()
    await update.message.reply_text("💰 Qual o *valor total* da compra? (em reais)\nEx: `2400` ou `2400.50`", parse_mode="Markdown")
    return VALOR


async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(update.message.text.strip().replace(",", "."))
        if valor <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Digite apenas números. Ex: `1200` ou `1200.50`", parse_mode="Markdown")
        return VALOR
    context.user_data["valor_total"] = valor
    await update.message.reply_text("🔢 Em *quantas parcelas*?\nEx: `12`", parse_mode="Markdown")
    return TOTAL_PARCELAS


async def receber_total_parcelas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        total = int(update.message.text.strip())
        if total < 1 or total > 120:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Número inválido. Digite entre 1 e 120.")
        return TOTAL_PARCELAS
    context.user_data["total_parcelas"] = total
    await update.message.reply_text(
        f"📍 Qual parcela você está pagando *agora*?\n"
        f"(1 se for a primeira, 2 se for a segunda...)\nEx: `1`",
        parse_mode="Markdown"
    )
    return PARCELA_ATUAL


async def receber_parcela_atual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        atual = int(update.message.text.strip())
        total = context.user_data["total_parcelas"]
        if atual < 1 or atual > total:
            raise ValueError
    except ValueError:
        total = context.user_data["total_parcelas"]
        await update.message.reply_text(f"❌ Digite um número entre 1 e {total}.")
        return PARCELA_ATUAL
    context.user_data["parcela_atual"] = atual
    await update.message.reply_text("📅 Qual o *dia do vencimento* todo mês?\nEx: `10`", parse_mode="Markdown")
    return VENCIMENTO


async def receber_vencimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dia = int(update.message.text.strip())
        if dia < 1 or dia > 31:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Dia inválido. Digite entre 1 e 31.")
        return VENCIMENTO

    context.user_data["dia_vencimento"] = dia
    dados = context.user_data
    user_id = update.effective_user.id

    # Salvar no banco
    with get_db() as db:
        parcela = criar_parcela(db, user_id, dados)
        total_mensal = total_mensal_parcelas(db, user_id)

    # Calcular data de término
    meses_restantes = parcela.total_parcelas - parcela.parcela_atual
    data_termino = date.today().replace(day=1)
    
    # Lógica para adicionar meses corretamente
    ano = data_termino.year + (data_termino.month + meses_restantes - 1) // 12
    mes = (data_termino.month + meses_restantes - 1) % 12 + 1
    data_termino = data_termino.replace(year=ano, month=mes)

    # Gerar dica com IA
    dica = await gerar_dica_parcela({
        "descricao": parcela.descricao,
        "valor_parcela": parcela.valor_parcela,
        "total_parcelas": parcela.total_parcelas,
        "parcelas_restantes": parcela.parcelas_restantes,
        "total_mensal_ativo": total_mensal,
        "data_termino": data_termino.strftime("%b/%Y"),
    })

    await update.message.reply_text(
        f"✅ *{parcela.descricao}* registrada!\n\n"
        f"💳 Cartão: **** {parcela.cartao_final}\n"
        f"💰 {parcela.total_parcelas}x de *R$ {parcela.valor_parcela:.2f}*\n"
        f"📊 Parcela {parcela.parcela_atual}/{parcela.total_parcelas} "
        f"— {parcela.parcelas_restantes} restantes\n"
        f"📅 Vence todo dia {parcela.dia_vencimento}\n"
        f"💸 Ainda a pagar: *R$ {parcela.valor_restante:.2f}*\n"
        f"🏁 Termina em: {data_termino.strftime('%b/%Y')}\n\n"
        f"💡 {dica}",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Registro cancelado.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── /parcelas ─────────────────────────────────────────────────

async def listar_parcelas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cartao_filtro = context.args[0] if context.args else None

    with get_db() as db:
        parcelas = listar_parcelas_ativas(db, user_id, cartao=cartao_filtro)
        total_mensal = total_mensal_parcelas(db, user_id)

    if not parcelas:
        filtro_txt = f" do cartão {cartao_filtro}" if cartao_filtro else ""
        await update.message.reply_text(f"✅ Nenhuma parcela ativa{filtro_txt}.")
        return

    # Agrupar por cartão
    cartoes = {}
    for p in parcelas:
        cartoes.setdefault(p.cartao_final, []).append(p)

    linhas = []
    for cartao, itens in cartoes.items():
        linhas.append(f"💳 *Cartão **** {cartao}*")
        for p in itens:
            barra = _barra_progresso(p.parcela_atual, p.total_parcelas)
            linhas.append(
                f"  `#{p.id}` {p.descricao}\n"
                f"  R$ {p.valor_parcela:.2f} ({p.parcela_atual}/{p.total_parcelas}) "
                f"— dia {p.dia_vencimento}\n"
                f"  {barra}"
            )
        linhas.append("")

    linhas.append(f"──────────────────")
    linhas.append(f"📊 Total comprometido/mês: *R$ {total_mensal:.2f}*")

    # Próximo vencimento
    if parcelas:
        hoje = date.today().day
        proximos = sorted(parcelas, key=lambda p: (
            p.dia_vencimento if p.dia_vencimento >= hoje
            else p.dia_vencimento + 31
        ))
        prox = proximos[0]
        diff = prox.dia_vencimento - hoje if prox.dia_vencimento >= hoje else (31 - hoje + prox.dia_vencimento)
        linhas.append(f"📅 Próximo vencimento: dia {prox.dia_vencimento} (daqui {diff} dias)")

    await update.message.reply_text("\n".join(linhas), parse_mode="Markdown")


# ── /quitar ───────────────────────────────────────────────────

async def quitar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Use: `/quitar [id]`\nConsulte os IDs com /parcelas",
            parse_mode="Markdown"
        )
        return

    try:
        parcela_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")
        return

    with get_db() as db:
        sucesso = quitar_parcela(db, parcela_id, update.effective_user.id)

    if sucesso:
        await update.message.reply_text(f"✅ Parcela `#{parcela_id}` marcada como quitada!", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Parcela não encontrada.")


# ── /proximo-mes ──────────────────────────────────────────────

async def proximo_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db() as db:
        parcelas = listar_parcelas_ativas(db, user_id)

    # Filtra parcelas que ainda terão parcelas no próximo mês
    ativas_proximo = [p for p in parcelas if p.parcelas_restantes > 0]
    total = sum(p.valor_parcela for p in ativas_proximo)

    if not ativas_proximo:
        await update.message.reply_text("✅ Nenhuma parcela prevista para o próximo mês!")
        return

    linhas = ["📅 *Parcelas do próximo mês:*\n"]
    for p in sorted(ativas_proximo, key=lambda x: x.dia_vencimento):
        linhas.append(f"• {p.descricao} (**** {p.cartao_final}) — R$ {p.valor_parcela:.2f} — dia {p.dia_vencimento}")

    linhas.append(f"\n💸 *Total: R$ {total:.2f}*")
    await update.message.reply_text("\n".join(linhas), parse_mode="Markdown")


# ── Utilitário ────────────────────────────────────────────────

def _barra_progresso(atual: int, total: int, tamanho: int = 10) -> str:
    preenchido = round((atual / total) * tamanho)
    return "█" * preenchido + "░" * (tamanho - preenchido) + f" {atual}/{total}"


# ── Registrar handlers ────────────────────────────────────────

def get_parcela_handlers():
    conv = ConversationHandler(
        entry_points=[CommandHandler("add_parcela", start_add_parcela)],
        states={
            CARTAO:          [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_cartao)],
            DESCRICAO:       [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            VALOR:           [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            TOTAL_PARCELAS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_total_parcelas)],
            PARCELA_ATUAL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_parcela_atual)],
            VENCIMENTO:      [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_vencimento)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        conversation_timeout=300  # 5 min sem resposta cancela
    )
    return [
        conv,
        CommandHandler("parcelas", listar_parcelas),
        CommandHandler("quitar", quitar),
        CommandHandler("proximo_mes", proximo_mes),
    ]
