from telegram import Update
from telegram.ext import ContextTypes
from ..database import crud
from datetime import datetime, timedelta

async def hoje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hoje_data = datetime.now().date()
    gastos = crud.get_gastos_periodo(user_id, hoje_data, hoje_data)
    total = sum(g.valor for g in gastos)
    
    msg = f"📅 *Gastos de Hoje ({hoje_data.strftime('%d/%m')})*\n\n"
    if not gastos:
        msg += "Nenhum gasto registrado."
    else:
        msg += f"💰 Total: R$ {total:.2f}\n\n"
        for g in gastos:
            desc = f" ({g.descricao})" if g.descricao else ""
            msg += f"• {g.categoria.capitalize()}: R$ {g.valor:.2f}{desc}\n"
            
    await update.message.reply_text(msg, parse_mode='Markdown')

async def semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hoje_data = datetime.now().date()
    inicio_semana = hoje_data - timedelta(days=hoje_data.weekday())
    gastos = crud.get_gastos_periodo(user_id, inicio_semana, hoje_data)
    total = sum(g.valor for g in gastos)
    
    msg = f"📅 *Gastos da Semana*\n\n"
    msg += f"💰 Total: R$ {total:.2f}\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    agora = datetime.now()
    mes_atual = agora.month
    ano_atual = agora.year
    
    gastos = crud.get_gastos_mes(user_id, mes_atual, ano_atual)
    total = sum(g.valor for g in gastos)
    
    msg = f"📅 *Resumo de {mes_atual}/{ano_atual}*\n\n"
    msg += f"💸 Total: R$ {total:.2f}\n\n"
    
    cats = crud.get_gastos_por_categoria(user_id, mes_atual, ano_atual)
    # Sort by total desc
    cats.sort(key=lambda x: x['total'], reverse=True)
    
    if not cats:
        msg += "Nenhum gasto este mês."
    else:
        msg += "Por categoria:\n"
        for c in cats:
            # Simple bar logic
            # Assuming max budget or just relative
            # Just text for now as per requirements
            msg += f"• {c['categoria'].capitalize()}: R$ {c['total']:.2f}\n"
        
    await update.message.reply_text(msg, parse_mode='Markdown')

async def categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await mes(update, context)
