from telegram import Update
from telegram.ext import ContextTypes
from ..services import parser
from ..database import crud
from datetime import datetime

async def dica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    agora = datetime.now()
    
    await update.message.reply_chat_action("typing")
    
    # Gather data for AI
    total_mes = crud.get_total_mes(user_id, agora.month, agora.year)
    cats = crud.get_gastos_por_categoria(user_id, agora.month, agora.year)
    
    # Construct data string
    dados_str = f"Dados do mês ({agora.month}/{agora.year}):\n"
    dados_str += f"- Total gasto: R$ {total_mes:.2f}\n"
    dados_str += "- Por categoria: " + str([{c['categoria']: c['total']} for c in cats]) + "\n"
    
    # Média diária (approx)
    dia = agora.day
    media = total_mes / dia if dia > 0 else 0
    dados_str += f"- Média diária: R$ {media:.2f}\n"
    
    try:
        relatorio = await parser.analise_mensal(dados_str)
        await update.message.reply_text(relatorio, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text("Desculpe, não consegui gerar uma dica agora.")
