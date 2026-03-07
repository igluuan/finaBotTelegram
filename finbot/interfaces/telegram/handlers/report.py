from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from finbot.database.connection import get_db
from finbot.database.repositories.expense_repository import ExpenseRepository
from finbot.database.repositories.earning_repository import EarningRepository
from finbot.database.repositories.installment_repository import InstallmentRepository
from finbot.interfaces.telegram.decorators import ensure_user
from finbot.interfaces.telegram import ui

@ensure_user
async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_date = datetime.now().date()
    
    with get_db() as db:
        expenses = ExpenseRepository.get_by_period(db, user_id, today_date, today_date)
        
    total = sum(g.amount for g in expenses)
    msg = f"📅 *Gastos de Hoje* ({today_date.strftime('%d/%m')}):\n\n"
    
    if not expenses:
        msg += "Nenhum gasto registrado."
    else:
        for g in expenses:
            name = g.description if g.description else g.category.capitalize()
            msg += f"• {name}: R$ {g.amount:.2f}\n"
        msg += f"\n🔴 *Total: R$ {total:.2f}*"
        
    await update.message.reply_text(msg, parse_mode="Markdown")

@ensure_user
async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_date = datetime.now().date()
    start_week = today_date - timedelta(days=today_date.weekday())
    
    with get_db() as db:
        expenses = ExpenseRepository.get_by_period(db, user_id, start_week, today_date)
        
    total = sum(g.amount for g in expenses)
    
    msg = f"📅 *Gastos da Semana* ({start_week.strftime('%d/%m')} - {today_date.strftime('%d/%m')}):\n\n"
    
    if not expenses:
        msg += "Nenhum gasto registrado nesta semana."
    else:
        # Group by category
        cats = {}
        for g in expenses:
            c = g.category.capitalize()
            cats[c] = cats.get(c, 0) + g.amount
        
        sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
        
        for cat, val in sorted_cats:
            msg += f"• {cat}: R$ {val:.2f}\n"
            
        msg += f"\n🔴 *Total da Semana: R$ {total:.2f}*"
        
    await update.message.reply_text(msg, parse_mode="Markdown")

@ensure_user
async def month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    with get_db() as db:
        total_earnings = EarningRepository.get_current_month_total(db, user_id)
        total_expenses = ExpenseRepository.get_current_month_total(db, user_id)
        total_installments = InstallmentRepository.get_monthly_total(db, user_id)
        
    msg = ui.format_balance(total_earnings, total_expenses, total_installments)
    await update.message.reply_text(msg, parse_mode="Markdown")

@ensure_user
async def categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now()
    
    with get_db() as db:
        expenses_cat = ExpenseRepository.get_by_category_monthly(db, user_id, now.month, now.year)
    
    msg = f"📂 *Gastos por Categoria ({now.strftime('%m/%Y')})*\n\n"
    
    if not expenses_cat:
        msg += "Nenhum gasto registrado neste mês."
    else:
        expenses_cat.sort(key=lambda x: x['total'], reverse=True)
        total_month = sum(item['total'] for item in expenses_cat)
        
        for item in expenses_cat:
            percentage = (item['total'] / total_month * 100) if total_month > 0 else 0
            msg += f"• *{item['category'].capitalize()}*: R$ {item['total']:.2f} ({percentage:.1f}%)\n"
            
        msg += f"\n🔴 *Total Geral: R$ {total_month:.2f}*"
        
    await update.message.reply_text(msg, parse_mode="Markdown")
