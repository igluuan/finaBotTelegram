from telegram import Update, InputFile
from telegram.ext import ContextTypes
from io import StringIO
from ..database import crud

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Ensure user exists
    existing_user = crud.get_user(user.id)
    if not existing_user:
        crud.create_user(user.id, user.first_name)
    
    await update.message.reply_text(
        f"Olá {user.first_name}! Sou o FinBot 💰.\n\n"
        "Eu ajudo você a controlar seus gastos de forma simples.\n"
        "Apenas me diga o que gastou, exemplo:\n"
        "👉 *'35 uber'* ou *'almoço 20'*\n\n"
        "Use /ajuda para ver o que posso fazer.",
        parse_mode='Markdown'
    )

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """
🤖 *Comandos do FinBot*

📌 *Geral*
/start - Iniciar conversa
/ajuda - Ver esta lista
/dica - Receber dica financeira da IA

📝 *Gastos*
_(Basta digitar o gasto, ex: "35 uber")_
/hoje - Resumo de gastos do dia
/semana - Resumo da semana
/mes - Resumo do mês
/categorias - Gastos por categoria
/orcamento [cat] [valor] - Definir meta mensal
/deletar - Apagar último gasto registrado

💳 *Parcelas*
/add\_parcela - Registrar compra parcelada
/parcelas - Listar parcelas ativas
/quitar [id] - Marcar parcela como paga
/proximo\_mes - Previsão de parcelas futuras

💵 *Ganhos*
/add\_ganho - Registrar entrada (salário, extra)
/ganhos - Ver ganhos e balanço do mês
"""
    await update.message.reply_text(msg, parse_mode='Markdown')

async def orcamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /orcamento [cat] [valor]
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Use: /orcamento [categoria] [valor]")
        return
        
    categoria = args[0].lower()
    try:
        valor = float(args[1].replace(',', '.'))
    except ValueError:
        await update.message.reply_text("Valor inválido.")
        return
        
    from datetime import datetime
    agora = datetime.now()
    user_id = update.effective_user.id
    
    crud.set_orcamento(user_id, categoria, agora.month, agora.year, valor)
    await update.message.reply_text(f"✅ Orçamento de *{categoria}* definido para R$ {valor:.2f}", parse_mode='Markdown')

async def deletar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    gasto = crud.delete_last_gasto(user_id)
    if gasto:
        await update.message.reply_text(f"🗑️ Gasto de R$ {gasto.valor:.2f} ({gasto.categoria}) removido.")
    else:
        await update.message.reply_text("Nenhum gasto para remover.")

async def exportar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    from datetime import datetime
    agora = datetime.now()
    gastos = crud.get_gastos_mes(user_id, agora.month, agora.year)
    ganhos = []
    try:
        from ..database import crud as crud_mod
        with crud_mod.get_db() as db:
            ganhos = crud_mod.listar_ganhos_mes(db, user_id)
    except Exception:
        ganhos = []
    buffer = StringIO()
    buffer.write("tipo,data,valor,categoria,descricao\n")
    for g in gastos:
        buffer.write(f"gasto,{g.data.isoformat()},{g.valor:.2f},{g.categoria},{(g.descricao or '').replace(',', ' ')}\n")
    for gan in ganhos:
        buffer.write(f"ganho,{gan.data.isoformat()},{gan.valor:.2f},{gan.categoria},{(gan.descricao or '').replace(',', ' ')}\n")
    buffer.seek(0)
    nome_arquivo = f"finbot_{agora.year}_{agora.month:02d}.csv"
    await update.message.reply_document(
        document=InputFile(buffer, filename=nome_arquivo),
        caption=f"Exportação de {agora.month}/{agora.year}."
    )
