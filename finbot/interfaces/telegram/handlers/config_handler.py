from telegram import Update
from telegram.ext import ContextTypes
from io import StringIO, BytesIO
from datetime import datetime
from finbot.database.connection import get_db
from finbot.database.repositories.expense_repository import ExpenseRepository
from finbot.database.repositories.budget_repository import BudgetRepository
from finbot.database.repositories.earning_repository import EarningRepository
from finbot.interfaces.telegram.decorators import ensure_user

@ensure_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Olá {user.first_name}! Sou o FinBot 💰.\n\n"
        "Eu ajudo você a controlar seus gastos de forma simples.\n"
        "Apenas me diga o que gastou, exemplo:\n"
        "👉 *'35 uber'* ou *'almoço 20'*\n\n"
        "Use /ajuda para ver o que posso fazer.",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """
🤖 *Comandos do FinBot*

📌 *Início & Configuração*
/start - Fazer cadastro inicial ou reiniciar
/ajuda - Ver esta lista
/dica - Receber dica financeira da IA

📝 *Gastos*
_(Basta digitar: "35 uber", "almoço 20")_
/hoje - Resumo do dia
/semana - Resumo da semana
/mes - Resumo do mês
/categorias - Gastos por categoria
/orcamento [cat] [valor] - Definir meta (Ex: /orcamento lazer 200)
/deletar - Apagar último gasto
/exportar - Baixar planilha (CSV) dos dados

💳 *Cartão & Parcelas*
/add_parcela - Registrar compra parcelada
/parcelas - Listar faturas e parcelas ativas
/proximo_mes - Previsão do próximo mês
/quitar [id] - Adiantar/Pagar parcela

/add_cartao - Cadastrar cartão (4 dígitos)
/cartoes - Listar cartoes cadastrados
/del_cartao - Remover cartão

💵 *Renda & Ganhos*
/add_ganho - Registrar salário ou extra
/ganhos - Ver entradas e saldo líquido
"""
    await update.message.reply_text(msg, parse_mode='Markdown')

@ensure_user
async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /orcamento [cat] [value]
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Use: /orcamento [categoria] [valor]")
        return
        
    category = args[0].lower()
    try:
        limit = float(args[1].replace(',', '.'))
    except ValueError:
        await update.message.reply_text("Valor inválido.")
        return
        
    now = datetime.now()
    user_id = update.effective_user.id
    
    with get_db() as db:
        BudgetRepository.set_budget(db, user_id, category, now.month, now.year, limit)
        
    await update.message.reply_text(f"✅ Orçamento de *{category}* definido para R$ {limit:.2f}", parse_mode='Markdown')

@ensure_user
async def delete_last_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    with get_db() as db:
        expense = ExpenseRepository.delete_last(db, user_id)
        
    if expense:
        await update.message.reply_text(f"🗑️ Gasto de R$ {expense.amount:.2f} ({expense.category}) removido.")
    else:
        await update.message.reply_text("Nenhum gasto para remover.")

@ensure_user
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now()
    
    with get_db() as db:
        expenses = ExpenseRepository.get_by_month(db, user_id, now.month, now.year)
        earnings = EarningRepository.get_current_month_earnings(db, user_id)
        
    buffer = StringIO()
    buffer.write("tipo,data,valor,categoria,descricao,metodo\n")
    
    for g in expenses:
        desc = (g.description or '').replace(',', ' ')
        method = g.payment_method or ''
        buffer.write(f"gasto,{g.date.isoformat()},{g.amount:.2f},{g.category},{desc},{method}\n")
        
    for e in earnings:
        desc = (e.description or '').replace(',', ' ')
        buffer.write(f"ganho,{e.date.isoformat()},{e.amount:.2f},{e.category},{desc},\n")
        
    buffer.seek(0)
    
    # Telegram requires bytes for InputFile from memory
    bytes_buffer = BytesIO(buffer.getvalue().encode('utf-8'))
    
    filename = f"finbot_{now.year}_{now.month:02d}.csv"
    await update.message.reply_document(
        document=bytes_buffer,
        filename=filename,
        caption=f"Exportação de {now.month}/{now.year}."
    )
