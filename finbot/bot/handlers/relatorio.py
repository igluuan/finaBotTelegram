from telegram import Update
from telegram.ext import ContextTypes
from ..database import crud
from datetime import datetime, timedelta
from ..decorators import garantir_usuario

@garantir_usuario
async def hoje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hoje_data = datetime.now().date()
    gastos = crud.get_gastos_periodo(user_id, hoje_data, hoje_data)
    total = sum(g.valor for g in gastos)
    
    msg = f"📅 *Gastos de Hoje ({hoje_data.strftime('%d/%m')})*\n\n"
    if not gastos:
        msg += "Nenhum gasto registrado."
    else:
        msg += f"💰 *Total: R$ {total:.2f}*".replace('.', ',') + "\n\n"
        for g in gastos:
            # Nome principal: Descrição ou Categoria
            nome = g.descricao if g.descricao else g.categoria.capitalize()
            # Metodo com traço
            metodo = f" - {g.metodo_pagamento}" if g.metodo_pagamento else ""
            
            # Formata valor
            valor_fmt = f"R$ {g.valor:.2f}".replace('.', ',')
            
            # Ex: • Uber: R$ 25,00 - Nubank 7766
            msg += f"• {nome}: *{valor_fmt}*{metodo}\n"
            
    await update.message.reply_text(msg, parse_mode='Markdown')

@garantir_usuario
async def semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hoje_data = datetime.now().date()
    inicio_semana = hoje_data - timedelta(days=hoje_data.weekday())
    gastos = crud.get_gastos_periodo(user_id, inicio_semana, hoje_data)
    total = sum(g.valor for g in gastos)
    
    msg = f"📅 *Gastos da Semana*\n\n"
    msg += f"💰 *Total: R$ {total:.2f}*".replace('.', ',') + "\n\n"
    
    if gastos:
        # Agrupa por método
        metodos = {}
        cats = {}
        
        for g in gastos:
            m = g.metodo_pagamento or "Outros"
            metodos[m] = metodos.get(m, 0) + g.valor
            
            c = g.categoria.capitalize()
            cats[c] = cats.get(c, 0) + g.valor
            
        msg += "*💳 Por método:*\n"
        for m, val in sorted(metodos.items(), key=lambda x: x[1], reverse=True):
             val_fmt = f"R$ {val:.2f}".replace('.', ',')
             msg += f"• {m}: {val_fmt}\n"
        
        msg += "\n*📂 Por categoria:*\n"
        for c, val in sorted(cats.items(), key=lambda x: x[1], reverse=True):
             val_fmt = f"R$ {val:.2f}".replace('.', ',')
             msg += f"• {c}: {val_fmt}\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

@garantir_usuario
async def mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    agora = datetime.now()
    mes_atual = agora.month
    ano_atual = agora.year
    
    gastos = crud.get_gastos_mes(user_id, mes_atual, ano_atual)
    total = sum(g.valor for g in gastos)
    
    msg = f"📅 *Resumo de {mes_atual}/{ano_atual}*\n\n"
    msg += f"💸 *Total: R$ {total:.2f}*".replace('.', ',') + "\n\n"
    
    if gastos:
        # Agrupa por método
        metodos = {}
        for g in gastos:
            m = g.metodo_pagamento or "Outros"
            metodos[m] = metodos.get(m, 0) + g.valor
            
        msg += "*💳 Por método:*\n"
        for m, val in sorted(metodos.items(), key=lambda x: x[1], reverse=True):
             val_fmt = f"R$ {val:.2f}".replace('.', ',')
             msg += f"• {m}: {val_fmt}\n"
        msg += "\n"
    
    cats = crud.get_gastos_por_categoria(user_id, mes_atual, ano_atual)
    # Sort by total desc
    cats.sort(key=lambda x: x['total'], reverse=True)
    
    if not cats:
        msg += "Nenhum gasto este mês."
    else:
        msg += "*📂 Por categoria:*\n"
        for c in cats:
            val_fmt = f"R$ {c['total']:.2f}".replace('.', ',')
            msg += f"• {c['categoria'].capitalize()}: {val_fmt}\n"
        
    await update.message.reply_text(msg, parse_mode='Markdown')

@garantir_usuario
async def categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await mes(update, context)
