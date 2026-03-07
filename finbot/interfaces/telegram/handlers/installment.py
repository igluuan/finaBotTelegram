import logging
import asyncio
from datetime import date
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, filters
)
from finbot.database.connection import get_db
from finbot.database.repositories.installment_repository import InstallmentRepository
from finbot.services.ai_service import generate_installment_tip
from finbot.interfaces.telegram.decorators import ensure_user

logger = logging.getLogger(__name__)

# Conversation States
CARD, DESCRIPTION, AMOUNT, TOTAL_INSTALLMENTS, CURRENT_INSTALLMENT, DUE_DATE = range(6)

async def start_add_installment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💳 Vamos registrar uma parcela!\n\n"
        "Qual o *final do cartão*? (4 dígitos)\n"
        "Ex: `4521`",
        parse_mode="Markdown"
    )
    return CARD

async def receive_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card = update.message.text.strip()
    if not card.isdigit() or len(card) != 4:
        await update.message.reply_text("❌ Digite exatamente 4 dígitos. Ex: `4521`", parse_mode="Markdown")
        return CARD
    context.user_data["card_last_digits"] = card
    await update.message.reply_text("🛍️ Qual é a *descrição* da compra?\nEx: `TV Samsung 55'`", parse_mode="Markdown")
    return DESCRIPTION

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text.strip()
    await update.message.reply_text("💰 Qual o *valor total* da compra? (em reais)\nEx: `2400` ou `2400.50`", parse_mode="Markdown")
    return AMOUNT

async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.strip().replace(",", "."))
        if val <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Digite apenas números. Ex: `1200` ou `1200.50`", parse_mode="Markdown")
        return AMOUNT
    context.user_data["total_amount"] = val
    await update.message.reply_text("🔢 Em *quantas parcelas*?\nEx: `12`", parse_mode="Markdown")
    return TOTAL_INSTALLMENTS

async def receive_total_installments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        total = int(update.message.text.strip())
        if total < 1 or total > 120:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Número inválido. Digite entre 1 e 120.")
        return TOTAL_INSTALLMENTS
    context.user_data["total_installments"] = total
    await update.message.reply_text(
        f"📍 Qual parcela você está pagando *agora*?\n"
        f"(1 se for a primeira, 2 se for a segunda...)\nEx: `1`",
        parse_mode="Markdown"
    )
    return CURRENT_INSTALLMENT

async def receive_current_installment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        current = int(update.message.text.strip())
        total = context.user_data["total_installments"]
        if current < 1 or current > total:
            raise ValueError
    except ValueError:
        total = context.user_data["total_installments"]
        await update.message.reply_text(f"❌ Digite um número entre 1 e {total}.")
        return CURRENT_INSTALLMENT
    context.user_data["current_installment"] = current
    await update.message.reply_text("📅 Qual o *dia do vencimento* todo mês?\nEx: `10`", parse_mode="Markdown")
    return DUE_DATE

async def receive_due_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        day = int(update.message.text.strip())
        if day < 1 or day > 31:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Dia inválido. Digite entre 1 e 31.")
        return DUE_DATE

    context.user_data["due_day"] = day
    data = context.user_data
    user_id = update.effective_user.id

    # Save to DB (async)
    def save_installment():
        with get_db() as db:
            inst = InstallmentRepository.create(db, user_id, data)
            total = InstallmentRepository.get_monthly_total(db, user_id)
            return inst, total

    installment, total_monthly = await asyncio.to_thread(save_installment)

    # Calculate end date
    remaining_months = installment.total_installments - installment.current_installment
    end_date = date.today().replace(day=1)
    
    # Logic to add months correctly
    year = end_date.year + (end_date.month + remaining_months - 1) // 12
    month = (end_date.month + remaining_months - 1) % 12 + 1
    end_date = end_date.replace(year=year, month=month)

    # Generate tip with AI
    tip = await generate_installment_tip({
        "description": installment.description,
        "installment_amount": installment.installment_amount,
        "total_installments": installment.total_installments,
        "remaining_installments": installment.remaining_installments,
        "active_monthly_total": total_monthly,
        "end_date": end_date.strftime("%b/%Y"),
    })

    await update.message.reply_text(
        f"✅ *{installment.description}* registrada!\n\n"
        f"💳 Cartão: **** {installment.card_last_digits}\n"
        f"💰 {installment.total_installments}x de *R$ {installment.installment_amount:.2f}*\n"
        f"📊 Parcela {installment.current_installment}/{installment.total_installments} "
        f"— {installment.remaining_installments} restantes\n"
        f"📅 Vence todo dia {installment.due_day}\n"
        f"💸 Ainda a pagar: *R$ {installment.remaining_amount:.2f}*\n"
        f"🏁 Termina em: {end_date.strftime('%b/%Y')}\n\n"
        f"💡 {tip}",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Registro cancelado.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

@ensure_user
async def list_installments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # args in python-telegram-bot are in context.args
    card_filter = context.args[0] if context.args else None
    
    def fetch_installments():
        with get_db() as db:
            insts = InstallmentRepository.get_active_installments(db, user_id, card_last_digits=card_filter)
            total = InstallmentRepository.get_monthly_total(db, user_id)
            return insts, total

    installments, total_monthly = await asyncio.to_thread(fetch_installments)

    if not installments:
        filter_txt = f" do cartão {card_filter}" if card_filter else ""
        await update.message.reply_text(f"✅ Nenhuma parcela ativa{filter_txt}.")
        return

    # Group by card
    cards = {}
    for p in installments:
        cards.setdefault(p.card_last_digits, []).append(p)

    lines = []
    for card, items in cards.items():
        lines.append(f"💳 *Cartão **** {card}*")
        for p in items:
            bar = _progress_bar(p.current_installment, p.total_installments)
            lines.append(
                f"  `#{p.id}` {p.description}\n"
                f"  R$ {p.installment_amount:.2f} ({p.current_installment}/{p.total_installments}) "
                f"— dia {p.due_day}\n"
                f"  {bar}"
            )
        lines.append("")

    lines.append(f"──────────────────")
    lines.append(f"📊 Total comprometido/mês: *R$ {total_monthly:.2f}*")

    # Next due date
    if installments:
        today_day = date.today().day
        upcoming = sorted(installments, key=lambda p: (
            p.due_day if p.due_day >= today_day
            else p.due_day + 31
        ))
        next_inst = upcoming[0]
        diff = next_inst.due_day - today_day if next_inst.due_day >= today_day else (31 - today_day + next_inst.due_day)
        lines.append(f"📅 Próximo vencimento: dia {next_inst.due_day} (daqui {diff} dias)")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def pay_installment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Use: `/quitar [id]`\nConsulte os IDs com /parcelas",
            parse_mode="Markdown"
        )
        return

    try:
        installment_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")
        return
    
    user_id = update.effective_user.id
    
    def mark_paid():
        with get_db() as db:
            return InstallmentRepository.mark_as_paid(db, installment_id, user_id)

    success = await asyncio.to_thread(mark_paid)

    if success:
        await update.message.reply_text(f"✅ Parcela `#{installment_id}` marcada como quitada!", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Parcela não encontrada.")

async def next_month_projection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    def get_projection():
        with get_db() as db:
            return InstallmentRepository.get_active_installments(db, user_id)

    installments = await asyncio.to_thread(get_projection)

    # Filter installments that will still be active next month
    active_next = [p for p in installments if p.remaining_installments > 0]
    total = sum(p.installment_amount for p in active_next)

    if not active_next:
        await update.message.reply_text("✅ Nenhuma parcela prevista para o próximo mês!")
        return

    lines = ["📅 *Parcelas do próximo mês:*\n"]
    for p in sorted(active_next, key=lambda x: x.due_day):
        lines.append(f"• {p.description} (**** {p.card_last_digits}) — R$ {p.installment_amount:.2f} — dia {p.due_day}")

    lines.append(f"\n💸 *Total: R$ {total:.2f}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

def _progress_bar(current: int, total: int, size: int = 10) -> str:
    filled = round((current / total) * size)
    return "█" * filled + "░" * (size - filled) + f" {current}/{total}"

def get_installment_handlers():
    conv = ConversationHandler(
        entry_points=[CommandHandler("add_parcela", start_add_installment)],
        states={
            CARD:            [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_card)],
            DESCRIPTION:     [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
            AMOUNT:          [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)],
            TOTAL_INSTALLMENTS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_total_installments)],
            CURRENT_INSTALLMENT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_current_installment)],
            DUE_DATE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_due_date)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        conversation_timeout=300
    )
    return [
        conv,
        CommandHandler("parcelas", list_installments),
        CommandHandler("quitar", pay_installment),
        CommandHandler("proximo_mes", next_month_projection),
    ]
