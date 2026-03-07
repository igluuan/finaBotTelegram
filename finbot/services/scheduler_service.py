from apscheduler.schedulers.asyncio import AsyncIOScheduler
from finbot.core.config import ALLOWED_USER_ID
from finbot.database.connection import get_db
from finbot.database.repositories.expense_repository import ExpenseRepository
from finbot.database.repositories.installment_repository import InstallmentRepository
from finbot.database.repositories.earning_repository import EarningRepository
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def daily_job(application):
    if not ALLOWED_USER_ID:
        return
    try:
        user_id = int(ALLOWED_USER_ID)
        today = datetime.now().date()
        with get_db() as db:
            expenses = ExpenseRepository.get_by_period(db, user_id, today, today)
            total = sum(g.amount for g in expenses)
            
        if total > 0:
            msg = f"🔔 *Resumo do Dia*\n\nVocê gastou R$ {total:.2f} hoje.\n"
            for g in expenses:
                msg += f"- {g.category}: R$ {g.amount:.2f}\n"
            await application.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in daily job: {e}")

async def weekly_job(application):
    if not ALLOWED_USER_ID:
        return
    try:
        user_id = int(ALLOWED_USER_ID)
        msg = "📅 *Relatório Semanal*\n\nConfira seus gastos da semana com /semana"
        await application.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in weekly job: {e}")

async def monthly_job(application):
    if not ALLOWED_USER_ID:
        return
    try:
        user_id = int(ALLOWED_USER_ID)
        msg = "📅 *Relatório Mensal*\n\nO mês virou! Confira o fechamento com /mes e peça uma /dica para o próximo mês."
        await application.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in monthly job: {e}")

async def alert_due_dates(application):
    today = datetime.now().date()
    try:
        with get_db() as db:
            installments = InstallmentRepository.get_all_active(db)
            
        users = {}
        for p in installments:
            due_date = date(today.year, today.month, min(p.due_day, 28))
            diff = (due_date - today).days
            if 1 <= diff <= 3:
                users.setdefault(p.user_id, []).append((p, diff))
                
        for user_id, items in users.items():
            lines = ["⏰ *Parcelas vencendo em breve:*\n"]
            for p, diff in items:
                lines.append(
                    f"• {p.description} (**** {p.card_last_digits})\n"
                    f"  R$ {p.installment_amount:.2f} — vence em {diff} dia(s)"
                )
            await application.bot.send_message(
                chat_id=user_id,
                text="\n".join(lines),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in due date alert job: {e}")

async def remind_recurring_earnings(application):
    today = date.today()
    try:
        with get_db() as db:
            recurring_earnings = EarningRepository.get_recurring_by_day(db, today.day)
            
            for g in recurring_earnings:
                already_exists = EarningRepository.exists_in_month(
                    db, g.user_id, g.description, today.month, today.year
                )
                
                if not already_exists:
                    await application.bot.send_message(
                        chat_id=g.user_id,
                        text=f"💵 Lembrete: hoje é dia {today.day}, "
                             f"você costuma receber *{g.description}* (R$ {g.amount:.2f}).\n"
                             f"Já recebeu? Use /add_ganho para registrar.",
                        parse_mode="Markdown"
                    )
    except Exception as e:
        logger.error(f"Error in recurring earnings job: {e}")

def start_scheduler(application):
    scheduler.add_job(daily_job, 'cron', hour=21, minute=0, args=[application])
    scheduler.add_job(weekly_job, 'cron', day_of_week='mon', hour=8, minute=0, args=[application])
    scheduler.add_job(monthly_job, 'cron', day=1, hour=9, minute=0, args=[application])
    scheduler.add_job(alert_due_dates, 'cron', hour=9, minute=0, args=[application])
    scheduler.add_job(remind_recurring_earnings, 'cron', hour=8, minute=0, args=[application])
    scheduler.start()
